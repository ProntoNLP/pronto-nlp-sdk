extraMetadataColumns = []
extraMetadataColumn2Index = {}     # {'column': index}
docID2ExtraMetadata = {}           # {docID: [...]}


def AddNewExtraMetadataColumns(headers, fSkipFirstColumn):
  headerIndex2ColumnIndex = [-1 for _ in headers]
  for i in range((1 if fSkipFirstColumn else 0), len(headers)):
    if headers[i].startswith("_"): headerIndex2ColumnIndex[i] = -1;  continue
    if headers[i] not in extraMetadataColumn2Index:
      extraMetadataColumn2Index[headers[i]] = len(extraMetadataColumns)
      extraMetadataColumns.append(headers[i])
    headerIndex2ColumnIndex[i] = extraMetadataColumn2Index[headers[i]]
  return headerIndex2ColumnIndex


def ConvertExtraMetadataRow(row, headerIndex2ColumnIndex, fSkipFirstColumn):
  convertedRow = []
  for iH in range((1 if fSkipFirstColumn else 0), len(row)):
    iC = headerIndex2ColumnIndex[iH]
    if iC < 0: continue
    while len(convertedRow) <= iC: convertedRow.append("")
    convertedRow[iC] = row[iH]
  return convertedRow



DocIDsThatNeedExtraMetadata = None
DocIDsThatNeedExtraMetadata2IndexMap = None

def GetFirstBatchOfDocIDsToDownloadExtraMetadataForDocIDSet(docIDs, iMaxDocIDs):
  global DocIDsThatNeedExtraMetadata
  global DocIDsThatNeedExtraMetadata2IndexMap
  DocIDsThatNeedExtraMetadata = sorted(set(docID for docID in docIDs if docIDs and docID not in docID2ExtraMetadata))
  DocIDsThatNeedExtraMetadata2IndexMap = {docID:i for i, docID in enumerate(DocIDsThatNeedExtraMetadata)}
  iCount = len(DocIDsThatNeedExtraMetadata)
  return [GetNextBatchOfDocIDsToDownloadExtraMetadata(iMaxDocIDs), iCount]


def GetNextBatchOfDocIDsToDownloadExtraMetadata(iMaxDocIDs):
  global DocIDsThatNeedExtraMetadata
  global DocIDsThatNeedExtraMetadata2IndexMap
  if not DocIDsThatNeedExtraMetadata:
    DocIDsThatNeedExtraMetadata = None
    DocIDsThatNeedExtraMetadata2IndexMap = None
    return None

  #return DocIDsThatNeedExtraMetadata[:iMaxDocIDs]
  DocIDs = []
  for docID in DocIDsThatNeedExtraMetadata:
    if not docID: continue
    DocIDs.append(docID)
    if len(DocIDs) >= iMaxDocIDs: break
  return DocIDs



def AddNewExtraMetadata(data):
  headers, rows = data
  assert headers[0] == 'DocID'

  headerIndex2ColumnIndex = AddNewExtraMetadataColumns(headers, True)

  for row in rows:
    docID = row[0]
    if len(row) > 1:
      docID2ExtraMetadata[docID] = ConvertExtraMetadataRow(row, headerIndex2ColumnIndex, True)
    else:
      docID2ExtraMetadata[docID] = None

    i = DocIDsThatNeedExtraMetadata2IndexMap.get(docID, None)
    if i is not None:
      DocIDsThatNeedExtraMetadata[i] = None
      del DocIDsThatNeedExtraMetadata2IndexMap[docID]

  return len(DocIDsThatNeedExtraMetadata2IndexMap)


def GetExtraMetadataColumns():
  return extraMetadataColumns


def GetExtraMetadataColumnValues(dateTickerDocID):
  iPosTicker = dateTickerDocID.find(',') + 1
  iPosDocID = dateTickerDocID.find(',', iPosTicker) + 1
  docID = dateTickerDocID[iPosDocID:]
  values = docID2ExtraMetadata.get(docID, None)
  outValues = [MakeCSVField(v) for v in values] if values else []
  while len(outValues) < len(extraMetadataColumns): outValues.append("")
  return outValues


def MakeCSVField(s):
  if s.find(',') >= 0  or  s.find('"') >= 0  or s.find('\n') >= 0  or  s.find('\r') >= 0:
    return '"' + s.replace('"', '""') + '"'
  else:
    return s
