from pronto_nlp import macro

success = macro.process_document(
    input="tests/_DocForMacroTest.txt",
    output="output.csv",
    user="ilay@dooble.co.il",
    password="Ilay6969"
)
print(success)