Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = currentDir

pythonw = "pythonw.exe"
If fso.FileExists("C:\Users\34048\AppData\Local\Programs\Python\Python313\pythonw.exe") Then
    pythonw = "C:\Users\34048\AppData\Local\Programs\Python\Python313\pythonw.exe"
End If

WshShell.Run pythonw & " launcher.pyw", 0, False
