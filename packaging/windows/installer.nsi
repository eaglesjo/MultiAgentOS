Unicode True
Name "MultiAgentOS"
OutFile "dist\\MultiAgentOS-${APP_VERSION}-windows-x64-setup.exe"
InstallDir "$PROGRAMFILES64\\MultiAgentOS"
RequestExecutionLevel Admin
Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles
Section "MultiAgentOS"
  SetOutPath "$INSTDIR"
  File "dist\\multiagentos.exe"
  CreateDirectory "$SMPROGRAMS\\MultiAgentOS"
  CreateShortCut "$SMPROGRAMS\\MultiAgentOS\\MultiAgentOS.lnk" "$INSTDIR\\multiagentos.exe"
  WriteUninstaller "$INSTDIR\\uninstall.exe"
SectionEnd
Section "Uninstall"
  Delete "$SMPROGRAMS\\MultiAgentOS\\MultiAgentOS.lnk"
  RMDir "$SMPROGRAMS\\MultiAgentOS"
  Delete "$INSTDIR\\multiagentos.exe"
  Delete "$INSTDIR\\uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
