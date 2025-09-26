#!/usr/bin/env python3
import config
from http import client
from pydglab_ws import DGLabWSServer, Channel, StrengthOperationType, RetCode, StrengthData, FeedbackButton, PULSE_DATA_MAX_LENGTH
from config import ADDRESS
import qrcode
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from aiohttp import request, web
import asyncio
from concurrent.futures import ThreadPoolExecutor
import pulse_data
import random

current_strengths = dict()
punish_id_increment = 0
max_strength = {Channel.A: 0, Channel.B: 0}

if config.CHANNEL == 'A':
    channel = Channel.A
elif config.CHANNEL == 'B':
    channel = Channel.B
else:
    raise ValueError("Invalid channel in config")

def create_qrcode_window(address: str):
    """Create and return a configured tkinter window with QR code - synchronous function"""
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=4,
    )
    qr.add_data(address)
    qr.make(fit=True)
    
    # Create QR code image
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Create popup window
    root = tk.Tk()
    root.title("Scan QR Code to Connect")
    
    # Get screen dimensions
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    # Calculate adaptive window size based on QR code size and screen
    qr_width, qr_height = qr_img.size
    
    # Add padding and space for text/buttons
    padding = 40
    text_space = 120
    button_space = 60
    
    # Calculate window dimensions
    window_width = max(qr_width + padding, 350)  # Minimum 350px width
    window_height = qr_height + text_space + button_space + padding
    
    # Ensure window doesn't exceed 80% of screen size
    max_width = int(screen_width * 0.8)
    max_height = int(screen_height * 0.8)
    
    if window_width > max_width:
        window_width = max_width
    if window_height > max_height:
        window_height = max_height
    
    # Calculate center position
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    
    # Set window geometry and make it resizable
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    root.resizable(True, True)
    
    # Set minimum size
    root.minsize(350, 300)
    
    # Convert PIL image to PhotoImage
    photo = ImageTk.PhotoImage(qr_img)
    
    # Create and pack widgets
    label_title = ttk.Label(root, text="Scan this QR code with the DGLab app", font=("Arial", 12, "bold"))
    label_title.pack(pady=10)
    
    label_qr = ttk.Label(root, image=photo)
    label_qr.pack(pady=10)
    
    # CRITICAL: Keep reference to prevent garbage collection
    label_qr.image = photo
    
    label_url = ttk.Label(root, text=f"URL: {address}", wraplength=350, font=("Arial", 8))
    label_url.pack(pady=5)
    
    close_button = ttk.Button(root, text="Close", command=root.destroy)
    close_button.pack(pady=10)
    
    return root  # Return only root, photo reference is now stored in label_qr.image

async def display_qrcode(address: str):
    """Display QR code in a non-blocking way using asyncio"""
    loop = asyncio.get_event_loop()
    
    # Create window in main thread
    root = create_qrcode_window(address)
    
    # Use asyncio to handle GUI updates without blocking
    def update_gui():
        try:
            root.update_idletasks()
            root.update()
            return True
        except tk.TclError:
            # Window was closed
            return False
    
    # Schedule periodic updates
    async def gui_updater():
        while True:
            if not update_gui():
                break
            await asyncio.sleep(0.01)  # 10ms updates
    
    # Start the GUI updater as a background task
    task = asyncio.create_task(gui_updater())
    
    # Return immediately, GUI will continue updating in background
    return task

"""
    Make Coyote happy.
    Without this function, Coyote will stuck in disconnecting state.
    Also: maintaining the maximum strength value to avoid invalid attempts.
"""
async def reply_to_packets(server, client):
    try:
        async for data in client.data_generator():
            if data == RetCode.CLIENT_DISCONNECTED:
                print("App disconnected, attempting to rebind...")
                await client.rebind()
                print("Rebind successful.")
            elif isinstance(data, StrengthData):
                print(f"Received strength data: {data}")
                max_strength[Channel.A] = data.a_limit
                max_strength[Channel.B] = data.b_limit
            elif isinstance(data, FeedbackButton):
                print(f"Feedback button pressed: {data.name}")
    except asyncio.CancelledError:
        await server.remove_local_client(client._client_id)


async def update_strength(client):
    xs = sorted(list(current_strengths.values()), reverse=True)
    total_strength = min(
        sum(map(lambda x: x[0] // x[1], zip(xs, range(1, len(xs) + 1)))),
        max_strength[channel]
    )
    print(f"Updating strength to {total_strength}")
    await client.set_strength(channel, StrengthOperationType.SET_TO, total_strength)

def punish(client, taskgroup, amount, duration):
    print(f"Punish: amount={amount}, duration={duration}")
    async def do_punish():
        global current_strengths
        global punish_id_increment
        punish_id_increment += 1
        punish_id = punish_id_increment
        current_strengths[punish_id] = amount
        await update_strength(client)
        await asyncio.sleep(duration)
        del current_strengths[punish_id]
        await update_strength(client)
    taskgroup.create_task(do_punish())

def handle_silksong_message(client, taskgroup):
    async def handle(request: web.Request):
        if request.content_type != "application/json":
            return web.Response(status=415, text="Only application/json is accepted")
        try:
            data = await request.json()
        except Exception:
            return web.Response(status=400, text="Invalid JSON")
        event = data.get("event")
        if event is None:
            return web.Response(status=400, text="Missing 'event' field")
        print(f'Event received: {event}')
        if event == "PlayerDead":
            punish(client, taskgroup, config.AMOUNT_PLAYER_DEAD, config.DURATION_PLAYER_DEAD)
        elif event == "TakeHealth":
            try:
                damage_amount = int(data["data"]["amount"])
            except (KeyError, ValueError, TypeError):
                return web.Response(status=400, text="Invalid or missing 'amount' in data")
            punish(client, taskgroup, config.AMOUNT_TAKE_DAMAGE, config.DURATION_TAKE_DAMAGE * damage_amount)
        else:
            return web.Response(status=400, text="Unknown event type")
        return web.json_response({"ok": True})
    
    return handle

async def run_http_server_for_silksong_message(client, taskgroup, address="0.0.0.0", port=3329):
    app = web.Application()
    app.router.add_post('/', handle_silksong_message(client, taskgroup))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, address, port)
    await site.start()
    try:
        while True:
            await asyncio.sleep(3600)  # Keep running
    except asyncio.CancelledError:
        await runner.cleanup()

async def send_pulse(client):
    while True:
        pulse_name_value = random.choice(list(pulse_data.PULSE_DATA.items()))
        pulse_value = pulse_name_value[1] * config.PULSE_REPEAT_COUNT
        pulse_value = pulse_value[:PULSE_DATA_MAX_LENGTH]
        pulse_duration = len(pulse_value) * 0.1
        print(f"Sending pulse pattern: {pulse_name_value[0]} with duration {pulse_duration:.1f}s")
        await client.add_pulses(channel, *pulse_value)
        await asyncio.sleep(pulse_duration * 0.99)  # Slightly less than pulse duration to avoid lag

async def main():
    async with DGLabWSServer("0.0.0.0", 3328, 10) as server:
        local_client = server.new_local_client()
        # Get QR code
        url = local_client.get_qrcode(f"ws://{ADDRESS}:3328")
        await display_qrcode(url)

        # Wait for binding
        await local_client.bind()
        print(f"Successfully bound App {local_client.target_id}.")

        q = asyncio.Queue()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(send_pulse(local_client))
            tg.create_task(reply_to_packets(server, local_client))
            tg.create_task(run_http_server_for_silksong_message(local_client, tg))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())