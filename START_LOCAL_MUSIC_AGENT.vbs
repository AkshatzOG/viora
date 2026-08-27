Set shell = CreateObject("WScript.Shell")
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
pythonw = root & "\venv\Scripts\pythonw.exe"
shell.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & root & "\launcher.py" & Chr(34), 0, False
