from pronto_nlp import macro

print('Processing document')
allResults = macro.process_document(
    input="../samples/_DocForMacroTest.txt",
    output="output.csv",
    user="user@example.com",
    password="password"
)
print(allResults)