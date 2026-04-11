"""PitWall37 Bridge — Windows-side agent connecting iRacing to the pit wall.

Runs on the GPU box. Streams live telemetry, monitors setup changes,
and executes pit commands from PitWall37.

Requirements: pip install pyirsdk websockets
"""

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime, timezone

try:
    import irsdk
except ImportError:
    print("ERROR: pyirsdk not installed. Run: pip install pyirsdk")
    raise

try:
    import websockets
except ImportError:
    print("ERROR: websockets not installed. Run: pip install websockets")
    raise

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bridge")

# PitWall37 cloud server (Tailscale IP)
PITWALL_URL = "ws://100.85.186.91:3737/ws/bridge"
RECONNECT_DELAY = 5  # seconds between reconnect attempts
TELEMETRY_HZ = 10  # how often to send telemetry (10Hz is plenty for live display)
IRACING_POLL_HZ = 60  # how often to poll iRacing shared memory


class IRacingState:
    """Tracks iRacing connection and session state."""

    def __init__(self):
        self.ir = irsdk.IRSDK()
        self.connected = False
        self.last_setup_tick = -1
        self.last_session_id = None
        self.last_session_num = -1
        self.on_track = False
        self.in_garage = False

    def connect(self) -> bool:
        if self.connected:
            return True
        if self.ir.startup():
            self.connected = True
            log.info("Connected to iRacing")
            return True
        return False

    def disconnect(self):
        if self.connected:
            self.ir.shutdown()
            self.connected = False
            log.info("Disconnected from iRacing")

    def check_connection(self) -> bool:
        if not self.connected:
            return self.connect()
        # Check if iRacing is still running
        if not self.ir.is_initialized or not self.ir.is_connected:
            self.connected = False
            log.warning("iRacing connection lost")
            return False
        return True

    def get_session_info(self) -> dict | None:
        """Get current session info (car, track, etc)."""
        if not self.connected:
            return None
        try:
            weekend = self.ir["WeekendInfo"]
            driver = self.ir["DriverInfo"]
            return {
                "track": weekend.get("TrackDisplayName", ""),
                "track_config": weekend.get("TrackConfigName", ""),
                "track_id": weekend.get("TrackID", 0),
                "session_id": weekend.get("SessionID", 0),
                "car": driver.get("Drivers", [{}])[0].get("CarScreenName", ""),
                "car_id": driver.get("Drivers", [{}])[0].get("CarID", 0),
                "driver": driver.get("Drivers", [{}])[0].get("UserName", ""),
                "iracing_member_id": driver.get("Drivers", [{}])[0].get("UserID", 0),
            }
        except Exception as e:
            log.error(f"Error getting session info: {e}")
            return None

    def get_setup(self) -> dict | None:
        """Get current car setup. Returns None if unchanged since last call."""
        if not self.connected:
            return None
        try:
            tick = self.ir.get_session_info_update_by_key("CarSetup")
            if tick == self.last_setup_tick:
                return None  # unchanged
            self.last_setup_tick = tick
            return self.ir["CarSetup"]
        except Exception:
            return None

    def get_setup_force(self) -> dict | None:
        """Get current car setup regardless of whether it changed."""
        if not self.connected:
            return None
        try:
            self.last_setup_tick = self.ir.get_session_info_update_by_key("CarSetup")
            return self.ir["CarSetup"]
        except Exception:
            return None

    def get_telemetry(self) -> dict | None:
        """Get current telemetry snapshot."""
        if not self.connected:
            return None
        try:
            ir = self.ir
            return {
                "ts": time.time(),
                "lap": ir["Lap"],
                "lap_dist_pct": ir["LapDistPct"],
                "lap_time": ir["LapCurrentLapTime"],
                "last_lap_time": ir["LapLastLapTime"],
                "best_lap_time": ir["LapBestLapTime"],
                "speed": ir["Speed"],  # m/s
                "rpm": ir["RPM"],
                "gear": ir["Gear"],
                "throttle": ir["Throttle"],
                "brake": ir["Brake"],
                "steering": ir["SteeringWheelAngle"],
                "fuel_level": ir["FuelLevel"],
                "fuel_pct": ir["FuelLevelPct"],
                "on_track": ir["IsOnTrack"],
                "in_garage": ir["IsInGarage"],
                "session_time": ir["SessionTime"],
                "session_flags": ir["SessionFlags"],
                # Tire temps (surface, left/mid/right per corner)
                "tire_lf_temp": [ir["LFtempCL"], ir["LFtempCM"], ir["LFtempCR"]],
                "tire_rf_temp": [ir["RFtempCL"], ir["RFtempCM"], ir["RFtempCR"]],
                "tire_lr_temp": [ir["LRtempCL"], ir["LRtempCM"], ir["LRtempCR"]],
                "tire_rr_temp": [ir["RRtempCL"], ir["RRtempCM"], ir["RRtempCR"]],
                # Tire pressures
                "tire_lf_pressure": ir["LFpressure"],
                "tire_rf_pressure": ir["RFpressure"],
                "tire_lr_pressure": ir["LRpressure"],
                "tire_rr_pressure": ir["RRpressure"],
                # Ride height
                "ride_height_lf": ir["LFrideHeight"],
                "ride_height_rf": ir["RFrideHeight"],
                "ride_height_lr": ir["LRrideHeight"],
                "ride_height_rr": ir["RRrideHeight"],
                # Lat/Lon G
                "lat_accel": ir["LatAccel"],
                "lon_accel": ir["LongAccel"],
            }
        except Exception as e:
            log.debug(f"Telemetry read error: {e}")
            return None

    def pit_command(self, command: str, value: int = 0):
        """Send a pit command to iRacing."""
        if not self.connected:
            return False
        try:
            cmd_map = {
                "clear": irsdk.PitCommandMode.clear,
                "fuel": irsdk.PitCommandMode.fuel,
                "lf": irsdk.PitCommandMode.lf,
                "rf": irsdk.PitCommandMode.rf,
                "lr": irsdk.PitCommandMode.lr,
                "rr": irsdk.PitCommandMode.rr,
                "ws": irsdk.PitCommandMode.ws,
                "fast_repair": irsdk.PitCommandMode.fr,
                "clear_tires": irsdk.PitCommandMode.clear_tires,
            }
            mode = cmd_map.get(command)
            if mode is None:
                log.error(f"Unknown pit command: {command}")
                return False
            self.ir.pit_command(mode, value)
            log.info(f"Pit command sent: {command} = {value}")
            return True
        except Exception as e:
            log.error(f"Pit command error: {e}")
            return False

    def reload_textures(self):
        """Reload car textures (for Trading Paints updates)."""
        if not self.connected:
            return False
        try:
            self.ir.broadcast_msg(
                irsdk.BroadcastMsg.reload_textures,
                irsdk.ReloadTexturesMode.car_idx,
                0,  # own car
            )
            log.info("Texture reload triggered")
            return True
        except Exception as e:
            log.error(f"Texture reload error: {e}")
            return False

    def start_telemetry_recording(self):
        """Start IBT telemetry recording."""
        if not self.connected:
            return False
        try:
            self.ir.broadcast_msg(
                irsdk.BroadcastMsg.telem_command,
                irsdk.TelemCommandMode.start,
            )
            log.info("Telemetry recording started")
            return True
        except Exception as e:
            log.error(f"Telemetry start error: {e}")
            return False

    def stop_telemetry_recording(self):
        """Stop IBT telemetry recording."""
        if not self.connected:
            return False
        try:
            self.ir.broadcast_msg(
                irsdk.BroadcastMsg.telem_command,
                irsdk.TelemCommandMode.stop,
            )
            log.info("Telemetry recording stopped")
            return True
        except Exception as e:
            log.error(f"Telemetry stop error: {e}")
            return False


class PitWallBridge:
    """Main bridge connecting iRacing to PitWall37."""

    def __init__(self):
        self.iracing = IRacingState()
        self.ws = None
        self.running = True
        self.outbound_queue = asyncio.Queue(maxsize=100)
        self.telemetry_buffer = deque(maxlen=600)  # 1 min at 10Hz

    async def send(self, msg_type: str, data: dict):
        """Queue a message to send to PitWall37."""
        msg = {"type": msg_type, "data": data, "ts": time.time()}
        try:
            self.outbound_queue.put_nowait(msg)
        except asyncio.QueueFull:
            # Drop oldest if queue full (telemetry is fine to drop)
            try:
                self.outbound_queue.get_nowait()
                self.outbound_queue.put_nowait(msg)
            except asyncio.QueueEmpty:
                pass

    async def handle_command(self, msg: dict):
        """Handle a command from PitWall37."""
        cmd = msg.get("command")
        params = msg.get("params", {})

        if cmd == "pit":
            # Pit stop command: {"command": "pit", "params": {"fuel": 50, "lf": 165, ...}}
            for action, value in params.items():
                self.iracing.pit_command(action, int(value))
            await self.send("pit_ack", {"params": params})

        elif cmd == "get_setup":
            setup = self.iracing.get_setup_force()
            if setup:
                await self.send("setup", {"setup": setup})

        elif cmd == "get_session":
            info = self.iracing.get_session_info()
            if info:
                await self.send("session_info", info)

        elif cmd == "reload_textures":
            self.iracing.reload_textures()
            await self.send("texture_ack", {})

        elif cmd == "start_recording":
            self.iracing.start_telemetry_recording()
            await self.send("recording_ack", {"action": "start"})

        elif cmd == "stop_recording":
            self.iracing.stop_telemetry_recording()
            await self.send("recording_ack", {"action": "stop"})

        elif cmd == "ping":
            await self.send("pong", {})

        else:
            log.warning(f"Unknown command: {cmd}")

    async def iracing_loop(self):
        """Poll iRacing for telemetry and state changes."""
        telem_interval = 1.0 / TELEMETRY_HZ
        last_telem_send = 0
        last_on_track = None
        last_in_garage = None
        last_lap = -1

        while self.running:
            if not self.iracing.check_connection():
                await asyncio.sleep(2)
                continue

            now = time.time()

            # Check for setup changes
            setup = self.iracing.get_setup()
            if setup is not None:
                log.info(f"Setup changed (UpdateCount: {setup.get('UpdateCount')})")
                await self.send("setup_change", {"setup": setup})

            # Get telemetry
            telem = self.iracing.get_telemetry()
            if telem:
                self.telemetry_buffer.append(telem)

                # Detect state transitions
                on_track = telem.get("on_track", False)
                in_garage = telem.get("in_garage", False)
                current_lap = telem.get("lap", -1)

                if on_track != last_on_track:
                    if on_track:
                        log.info("Driver on track")
                        await self.send("state", {"event": "on_track"})
                    else:
                        log.info("Driver off track")
                        await self.send("state", {"event": "off_track"})
                    last_on_track = on_track

                if in_garage != last_in_garage:
                    if in_garage:
                        log.info("Driver in garage")
                        await self.send("state", {"event": "in_garage"})
                        # Auto-send setup when entering garage
                        full_setup = self.iracing.get_setup_force()
                        if full_setup:
                            await self.send("setup", {"setup": full_setup})
                    last_in_garage = in_garage

                # Detect new lap
                if current_lap > last_lap and last_lap >= 0:
                    last_lap_time = telem.get("last_lap_time", 0)
                    if last_lap_time and last_lap_time > 0:
                        log.info(f"Lap {last_lap} completed: {last_lap_time:.3f}s")
                        await self.send("lap_complete", {
                            "lap_number": last_lap,
                            "lap_time": last_lap_time,
                            "fuel_level": telem.get("fuel_level"),
                        })
                last_lap = current_lap

                # Send telemetry at configured rate
                if now - last_telem_send >= telem_interval:
                    await self.send("telemetry", telem)
                    last_telem_send = now

            await asyncio.sleep(1.0 / IRACING_POLL_HZ)

    async def ws_sender(self):
        """Send queued messages to PitWall37."""
        while self.running:
            if self.ws is None:
                await asyncio.sleep(0.1)
                continue
            try:
                msg = await asyncio.wait_for(
                    self.outbound_queue.get(), timeout=1.0
                )
                await self.ws.send(json.dumps(msg))
            except asyncio.TimeoutError:
                # Send heartbeat
                if self.ws:
                    try:
                        await self.ws.send(json.dumps({
                            "type": "heartbeat",
                            "ts": time.time(),
                            "iracing_connected": self.iracing.connected,
                        }))
                    except Exception:
                        pass
            except Exception as e:
                log.error(f"WS send error: {e}")

    async def ws_receiver(self):
        """Receive commands from PitWall37."""
        while self.running:
            if self.ws is None:
                await asyncio.sleep(0.1)
                continue
            try:
                raw = await self.ws.recv()
                msg = json.loads(raw)
                await self.handle_command(msg)
            except Exception as e:
                log.debug(f"WS receive error: {e}")
                break

    async def connect_pitwall(self):
        """Connect to PitWall37 WebSocket with reconnection."""
        while self.running:
            try:
                log.info(f"Connecting to PitWall37 at {PITWALL_URL}...")
                async with websockets.connect(
                    PITWALL_URL,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    self.ws = ws
                    log.info("Connected to PitWall37")

                    # Send initial state
                    await self.send("bridge_connect", {
                        "version": "1.0",
                        "iracing_connected": self.iracing.connected,
                        "hostname": __import__("socket").gethostname(),
                        "time": datetime.now(timezone.utc).isoformat(),
                    })

                    # If iRacing is connected, send session info
                    if self.iracing.connected:
                        info = self.iracing.get_session_info()
                        if info:
                            await self.send("session_info", info)
                        setup = self.iracing.get_setup_force()
                        if setup:
                            await self.send("setup", {"setup": setup})

                    # Run sender and receiver concurrently
                    await asyncio.gather(
                        self.ws_sender(),
                        self.ws_receiver(),
                    )

            except (
                websockets.exceptions.ConnectionClosed,
                ConnectionRefusedError,
                OSError,
            ) as e:
                self.ws = None
                log.warning(f"PitWall37 connection lost: {e}")
            except Exception as e:
                self.ws = None
                log.error(f"Unexpected error: {e}")

            log.info(f"Reconnecting in {RECONNECT_DELAY}s...")
            await asyncio.sleep(RECONNECT_DELAY)

    async def run(self):
        """Main entry point."""
        log.info("PitWall37 Bridge starting...")
        log.info(f"Target: {PITWALL_URL}")

        try:
            await asyncio.gather(
                self.iracing_loop(),
                self.connect_pitwall(),
            )
        except KeyboardInterrupt:
            log.info("Shutting down...")
            self.running = False
            self.iracing.disconnect()


def main():
    print()
    print("  ==========================================")
    print("       PitWall37 Bridge v1.0")
    print('       "He was built with Claude."')
    print("  ==========================================")
    print()
    bridge = PitWallBridge()
    asyncio.run(bridge.run())


if __name__ == "__main__":
    main()
