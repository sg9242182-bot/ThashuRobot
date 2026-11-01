# THASHU Flutter App Setup

## Project location

`D:\ThashuRobot-phase1\mobile\flutter`

## Tools used

- Flutter SDK: `D:\flutter`
- Flutter version checked: `3.47.8`
- Dart version checked: `3.13.7`
- Target: Android emulator or Android device

## Get the app ready

Open the VS Code terminal and enter the app folder:

```powershell
cd "D:\ThashuRobot-phase1\mobile\flutter"
```

## Download packages

Run this command in the VS Code terminal from the `mobile\flutter` folder:

`D:\flutter\bin\flutter.bat pub get`

Success looks like: `Got dependencies!`

## Run the app

Start the Android emulator. In the VS Code terminal, check its device ID:

`D:\flutter\bin\flutter.bat devices`

Then run the app, replacing `emulator-5554` with the ID shown above:

`D:\flutter\bin\flutter.bat run -d emulator-5554`