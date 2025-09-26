# SilksongCoyote
Punish the player for taking damage and dying in Hollow Knight: Silksong with Coyote.

Cross-platform, should work on any OS that runs silksong.

Expect bad and AI generated code.

If you need further assistence, I'm happy to help.

# Disclaimer

*Set the strength limit in the Coyote App!*

This program doesn't have security as a consideration, since it isn't expected to run on the internet. However, with the strength limit correctly set, nothing to bad could happen even if malicious requests appear.

The strength of multiple events can add-up in an attuned way: the n-th strongest strength has 1/n the original effect.

## CoyoteServer Usage

### Installation

First, install the required Python packages for the server:

```bash
cd CoyoteServer
pip install -r requirements.txt
```

### Configuration

Edit `config.py` to set your device address, channel, and punishment parameters:

```python
ADDRESS = '192.168.x.x'  # Set to your device/server address
CHANNEL = 'A'            # or 'B'
AMOUNT_TAKE_DAMAGE = 30  # Strength for damage event
DURATION_TAKE_DAMAGE = 1 # Duration for damage event
AMOUNT_PLAYER_DEAD = 100 # Strength for death event
DURATION_PLAYER_DEAD = 10 # Duration for death event
PULSE_REPEAT_COUNT = 5   # Number each pulse shape is repeated before a new random one is selected
```

### Running the Server

Start the server with:

```bash
python3 coyote.py
```

This will open a QR code window for device connection and start the HTTP server for Silksong message integration.

### Integrating with Silksong

Send HTTP requests to the server to trigger punishment events. The server listens for Silksong game events and applies configured pulses.

## Plugin

The Silksong plugin depends on [BepInEx 5](https://github.com/BepInEx/BepInEx).
After installing BepInEx 5, Copy SilksongCoyote.dll to the plugin directory.