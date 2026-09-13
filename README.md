# SilentNotifs

`Modified by ChatGPT 6.0 Astra`

Keep notification sounds silent while another app is playing audio. No settings
are required. Original tweak by dvntm.

## Why some apps were missed

Version 0.0.2 only checked `SBMediaController.isPlaying`, the system's media
playback state. Apps can output audio without being represented as the playing
Now Playing app. Examples to check include games, embedded videos and voice
messages; coverage depends on the app's audio implementation.

Version 0.0.3 keeps that check and also reads
`AVAudioSession.isOtherAudioPlaying` in SpringBoard. Apple's iOS 14.5 SDK header
explicitly says this property includes audio from apps using the mixable
`AVAudioSessionCategoryAmbient` category. The similarly named
`secondaryAudioShouldBeSilencedHint` only considers non-mixable sessions and is
not a suitable replacement here.

Reference: [Apple's isOtherAudioPlaying documentation](https://developer.apple.com/documentation/avfaudio/avaudiosession/isotheraudioplaying).
The detailed mixable-audio distinction is also documented in the iOS SDK's
`AVFAudio.framework/Headers/AVAudioSession.h`.

## Behavior

- Check live playback state each time SpringBoard decides whether to play a
  notification sound. There is no polling, sticky playback flag or timeout.
- Keep the original `com.apple.mobiletimer` exemption for Clock notifications,
  including alarms and timers. iOS still decides whether those sounds play.
- Keep the existing sound-only hook. Notification delivery, banners and
  vibration are not modified by this change.
- Do not change media volume, the mute switch, Focus/DND, or any audio-session
  category, mode or activation state.
- Guard the private media-controller selectors before calling them.

This detects the audio activity reported by iOS, not the amplitude of the audio
samples. An app playing a silent audio stream can still count as playing.
Audio produced entirely inside an app through its own custom alert code is
outside this SpringBoard notification hook.

## Install the included build

The included `.deb` is for **rootful iOS 14 or later**, with arm64 and arm64e
slices. It is intended for the iPhone SE (2020) on iOS 14.8 with unc0ver. It is
not a rootless package.

Open `packages/com.dvntm.silentnotifs_0.0.3_iphoneos-arm.deb` in a package
installer such as Zebra or Filza, install the update, then respring. The package
identifier is unchanged, so this replaces the existing SilentNotifs package.

For a root shell, from the directory containing the package:

```sh
dpkg -i com.dvntm.silentnotifs_0.0.3_iphoneos-arm.deb
killall SpringBoard
```

## Validation and on-device checks

The original author's README reported testing 0.0.2 on iOS 14.8 and iOS 16.4.1.
That claim does not apply to this modified build. Version 0.0.3 was cross-compiled
and its package and Mach-O structure checked; it has not been run on an iPhone
in this environment.

The Linux compiler emits the older arm64e ABI. The included package applies
the [allemande static ABI converter](https://github.com/p0358/allemande) to its
arm64e constant-string fixups before signing, following the conversion route
described in the [Theos documentation](https://theos.dev/docs/rootless).
The arm64 slice is unchanged by that conversion. No system-wide `oldabi` package
is required by this build. Conversion is not a substitute for device testing.

After installing, use a notification from another app to check:

| Scenario | Expected result |
| --- | --- |
| No app audio playing | Normal iOS notification sound behavior |
| Music/video represented in Now Playing | Notification sound suppressed |
| Previously missed app actively playing audio | Notification sound suppressed |
| Mixable game/Ambient audio playing | Notification sound suppressed |
| Playback stopped and no other app audio remains | Normal notification sound behavior returns |
| Clock alarm or timer while app audio plays | This tweak leaves the Clock sound decision to iOS |

Repeat the previously missed app check on the audio routes you use, such as the
speaker and Bluetooth. If it still fails, record the app name/version, iOS
version, audio route, and whether it appears in Now Playing.

## Build from source

With Theos and an iOS SDK:

```sh
make clean package FINALPACKAGE=1
```

Both build routes target iOS 14.0 or later; the package declares that firmware
dependency. Building with Theos on macOS and a compatible Xcode toolchain avoids
the Linux ABI-conversion step.

The optional `build.py` helper uses a Linux iOS toolchain, SDK, Logos, and Theos
headers/libraries already present on disk. It downloads nothing:

```sh
python3 build.py \
  --toolchain /path/to/toolchain/bin \
  --sdk /path/to/iPhoneOS.sdk \
  --logos /path/to/logos \
  --headers /path/to/theos/headers \
  --libraries /path/to/theos/lib \
  --abi-converter /path/to/allemande
```

The converter argument is required for a compiler that emits legacy arm64e
metadata. The helper refuses to package that output without conversion.
