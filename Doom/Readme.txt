Updated with doomv2 - shotgunfix


Classic Doom compiled for the Ingenic X2000 (XBurst + MSA) running on your K1 Max 3D printer!

## 🎮 Features

- Runs natively on K1 Max's Ingenic X2000 processor
- Compatible with all screen software (HelixScreen, CrealityScreen, GuppyScreen)
- Automatic framebuffer management
- Easy one-script installation

## ⚠️ Known Issues

**This is a work in progress!**

- **No audio** - Silent version only - Audio version requiers external device (for now)
- **Shotgun freeze** - Picking up the shotgun currently freezes the game (investigating)
- **Had trouble with the starting location, used warp to move to a safer place - could be issue with clipping

If you can help track down these issues, pull requests are welcome!

## 📦 Installation

### Quick Install

1. **Download files from (https://github.com/Mart7Mcfl7/K1maXburst/tree/main/Doom)**
   - `k1max-doom.tar.gz`
   - `install.sh`

2. **Upload to printer**
   - Use WinSCP, FileZilla, or `scp` to copy both files to `/usr/data/`

3. **SSH into your printer and run:**

   chmod +x /usr/data/install.sh
   /usr/data/install.sh

4. **Follow the on-screen instructions**

### Manual Installation ###

If you prefer to install manually:

cd /usr/data
tar -xzf k1max-doom.tar.gz -C /usr/data/Doom
chmod +x /usr/data/Doom/launch_doom.sh
chmod +x /usr/data/Doom/doom_k1max

## 🚀 Usage

Once installed, launch Doom:

cd /usr/data/Doom
./launch_doom.sh

The launcher will:
- Stop your screen software temporarily
- Clear the framebuffer
- Launch Doom on your printer's display

## 🎯 Controls

[USB keyboard support included, must be plugged in before game starts]

## 🔧 Technical Details

- **Platform:** Ingenic X2000 (XBurst + MSA)
- **Architecture:** MIPS32r2 Little Endian
- **Binary size:** ~5.2 MB
- **WAD file:** Doom 1 Shareware (~4.0 MB)
- **Total install:** ~9.5 MB

## 🛠️ Troubleshooting

**Screen stays black after launching:**
- The launcher kills screen software - this is normal
- Doom should appear within a few seconds

**"Permission denied" when running installer:**

chmod +x /usr/data/install.sh


**Want to restore screen software after playing:**

# For HelixScreen:
/usr/data/helixscreen/bin/helix-launcher.sh &

# For CrealityScreen:
CrealityScreen &

# For GuppyScreen:
guppyscreen &


## 📝 Uninstall

rm -rf /usr/data/Doom

## 🤝 Contributing

Found a bug? Have a fix for the shotgun freeze? Contributions welcome!

1. Fork the repo
2. Create your feature branch
3. Submit a pull request

## 📄 License

GPLv3

## 🙏 Credits

- Original Doom by id Software
- Compiled for Ingenic X2000/K1 Max by [Mart7Mcfl7]
- Creality K1 Max community

## ⚡ Performance

Runs surprisingly well on the X2000!Framerate is playable for the classic Doom experience.

---

**Enjoy fragging demons on your 3D printer! 🔥**
