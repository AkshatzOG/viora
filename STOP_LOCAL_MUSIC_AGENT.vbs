Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
On Error Resume Next
http.Open "POST", "http://127.0.0.1:8888/shutdown", False
http.Send "{}"
