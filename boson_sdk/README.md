# FLIR Boson SDK

This folder is where the app looks for the proprietary FLIR Boson SDK. It's
not included in this repository — FLIR distributes it separately.

## Setup

1. Download the Boson SDK from FLIR (you'll need a FLIR account):
   https://www.flir.com/support/products/boson/
2. Extract the SDK zip directly into this folder (`boson_sdk/`).
3. Launch the app. The startup log will confirm whether the SDK was found;
   without it, the app runs in video-only mode automatically — thermal
   imaging still works, just without SDK-side control (FFC, AGC/gain mode,
   palette LUT, radiometric mode) over the serial CCI channel.

You don't need to match any particular subfolder structure — whatever comes
out of FLIR's zip (their own internal layout has varied between SDK releases;
some nest an `SDK_USER_PERMISSIONS` folder inside another one of the same
name) is searched for automatically, up to a few levels deep.

## What "found" looks like

A correctly extracted SDK gives you a path like:

```
boson_sdk/
└── SDK_USER_PERMISSIONS/
    └── ClientFiles_Python/
        ├── Client_API.py
        └── EnumTypes.py
```

(or that same `SDK_USER_PERMISSIONS/` folder nested one level deeper, if
that's how FLIR's zip for your SDK version is packaged — either is fine).
