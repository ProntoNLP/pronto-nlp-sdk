"""
Below is a simple example of how to ingest and process Signal Updates from the SFTP

Please fill the following parameters:
KEY_PATH --> path to your SFTP key
USER_NAME --> user name for SFTP
TEMP_TABLE --> name of a temporary table in your database
TABLE --> name of the final signal scores table in your database
LAST_LOADED_TABLE --> name of tracking table in your database
columns_to_keep --> please adjust it to the columns you want to save

Also, implement the following as needed for your database operations

class called 'postggresHandler' with the following functions:

1. selectDatafromDB(query):
    - Function should run the query and return a pandas dataframe

2. `loadDataFromDfIntoTable(df, table_name, extra_param=None, truncate_before_load=False)`:
   - This function should load data from a pandas DataFrame into the specified table in your database.
   
3. `updateTableInDb(query)`:
   - This function should execute the given SQL query to perform any necessary updates or modifications to your database.
"""

import re
import paramiko
import postggresHandler as ph  # Custom module for handling PostgreSQL operations
import pandas as pd
from pathlib import Path
import os

# Define file path constants
KEY_PATH = Path("Path to SFTP Key")
assert (KEY_PATH.exists())  # Ensure the SFTP key exists
USER_NAME = "SFTP User Name"

# Define table names
TEMP_TABLE = 'temp_table'
TABLE = 'final_table'
LAST_LOADED_TABLE = 'last_tracking_file_table'


# Specify the columns to retain for the data update
columns_to_keep = ['signaltype', 'docid', 'gvkey', 'bestticker', 'docdate', 'aspectbasedclassifierscore',
                   'eventsscore_1_1_0', 'eventsscore_1_1_1', 'eventsscore_3_1_0', 'eventsscore_4_2_1']



class SignalSFTPClient:
    def __init__(self, hostname='sftp.prontonlp.net', port=22, username=None, private_key_path=None, passphrase=None):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.private_key_path = private_key_path
        self.passphrase = passphrase
        self.transport = None
        self.sftp = None

    def connect(self):
        self.transport = paramiko.Transport((self.hostname, self.port))
        if self.private_key_path:
            pkey = paramiko.RSAKey(filename=self.private_key_path, password=self.passphrase)
            self.transport.connect(username=self.username, pkey=pkey)
        else:
            self.transport.connect(username=self.username)
        self.sftp = paramiko.SFTPClient.from_transport(self.transport)

    def get_filenames(self, remote_directory='.'):
        return self.sftp.listdir(remote_directory)

    def get_filenames_sorted(self, remote_directory='.'):
        filenames = self.sftp.listdir(remote_directory)

        # Use a regex pattern to extract date and hour from filenames
        pattern = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{2})")

        # Filter filenames based on the pattern and sort in descending order of date and hour
        valid_filenames = [f for f in filenames if pattern.search(f)]
        valid_filenames.sort(key=lambda x: pattern.search(x).groups(), reverse=True)

        return valid_filenames

    def download(self, remote_filepath, local_filepath):
        self.sftp.get(remote_filepath, local_filepath)

    def close(self):
        self.sftp.close()
        self.transport.close()


def format_collection_for_sql_query(coll) -> str:
    """
    Cast to tuple since its repr uses (), which SQL requires
    For a collection of length 1, remove the final comma, ie ("item",) -> ("item"), since SQL doesn't accept this
    """
    res = tuple(coll)
    if len(res) == 1:
        return repr(res)[:-2] + ')'
    return repr(res)


# Function to retrieve the filename of the last loaded file from the database
def getLastLoadedFile():
    query = f'select filename from {LAST_LOADED_TABLE};'  # SQL query to get the last loaded filename
    lastLoadedFile = ph.selectDatafromDB(query)['FILENAME']  # Execute query and fetch filename
    return lastLoadedFile


# Main function for the process
def main():
    lastFile = getLastLoadedFile()[0]  # Get the last loaded file from the database
    client = SignalSFTPClient(username=USER_NAME, private_key_path=KEY_PATH)  # Initialize SFTP client
    client.connect()  # Connect to the SFTP server
    sig_fnames_sorted = client.get_filenames_sorted()  # Get list of files sorted by date
    lastSignalFile = sig_fnames_sorted[0]  # Get the latest signal file
    sig_fnames_sorted = sig_fnames_sorted[::-1]  # Reverse the list for processing from the oldest

    # If the latest file is different from the last loaded file, process it
    if lastSignalFile != lastFile:
        for file in sig_fnames_sorted:
            if file > lastFile:  # Process only files newer than the last loaded file
                print(f'loading file: {file}')
                client.download(file, file)  # Download the file
                df = pd.read_csv(file)  # Read the CSV file into a DataFrame
                df.columns = [x.lower() for x in df.columns]  # Convert all column names to lowercase

                # Handle rows flagged for deletion
                docsToDelete = df[df['signaltype'] == 'delete']['docid']  # Get IDs of documents to delete
                docsToDelete = format_collection_for_sql_query(docsToDelete)  # Format the IDs for SQL query

                # Delete records if there are any documents to delete
                if docsToDelete != '()':
                    delQuery = 'delete from {TABLE} where docid in {docsToDelete}'
                    ph.updateTableInDb(delQuery.format(TABLE=TABLE, docsToDelete=docsToDelete))

                df = df[df['signaltype'] != 'delete']  # Exclude deletion rows
                df = df[columns_to_keep]  # Filter to keep only the specified columns

                # Truncate the temporary table and load new data into it
                truncateQuery = f'truncate table {TEMP_TABLE};'
                ph.updateTableInDb(truncateQuery)
                ph.loadDataFromDfIntoTable(df, TEMP_TABLE, None, True)

                # Remove duplicate records from the temporary table
                deleteQuery = f'delete from {TEMP_TABLE} where docid in (select docid from {TABLE})'
                ph.updateTableInDb(deleteQuery)

                # Insert the new data from the temporary table into the main table
                insertQuery = f'insert into {TABLE} select * from {TEMP_TABLE}'
                ph.updateTableInDb(insertQuery)

                # Remove the local copy of the file after processing
                if os.path.exists(file):
                    os.remove(file)

                # Update the last loaded file table with the current file
                deleteQuery = f'truncate table {LAST_LOADED_TABLE};'
                ph.updateTableInDb(deleteQuery)
                insertQuery = f"insert into {LAST_LOADED_TABLE} VALUES ('{file}')"
                ph.updateTableInDb(insertQuery)
            else:
                break  # Stop processing if the file is older than the last loaded file



# Entry point of the script
if __name__ == "__main__":
    main()
