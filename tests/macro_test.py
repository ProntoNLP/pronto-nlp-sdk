from pronto_nlp import macro

success = macro.process_document(
    input="tests/_DocForMacroTest.txt",
    output="output.csv",
    user=org:user",
    password="password"
)
print(success)
