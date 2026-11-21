import json
import time
import websocket
import os
import requests
from dotenv import load_dotenv

load_dotenv()


class XboxController:
    def __init__(self):
        self.base_url = os.environ["HA_URL"].rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {os.environ['HA_TOKEN']}",
            "Content-Type": "application/json",
        }
        self.entity_id = "media_player.xbox"

    def get_status(self):
        response = requests.get(
            f"{self.base_url}/api/states/{self.entity_id}",
            headers=self.headers,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["state"]

    def _call_service(self, service, data=None):
        payload = {"entity_id": self.entity_id}
        if data:
            payload.update(data)

        response = requests.post(
            f"{self.base_url}/api/services/media_player/{service}",
            headers=self.headers,
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    
    def wait_until_ready(self, timeout=60):
        """Wait for the Xbox to finish powering on."""
        start = time.monotonic()

        while time.monotonic() - start < timeout:
            if self.get_status() == "on":
                return True
            time.sleep(2)

        raise TimeoutError("Xbox did not become ready in time")

    def get_installed_games(self):
        """Retrieve installed games from Home Assistant."""
        ws_url = (
            self.base_url.replace("http://", "ws://")
            .replace("https://", "wss://")
            + "/api/websocket"
        )

        ws = websocket.create_connection(ws_url, timeout=15)

        try:
            greeting = json.loads(ws.recv())
            if greeting.get("type") != "auth_required":
                raise RuntimeError(f"Unexpected greeting: {greeting}")

            ws.send(json.dumps({
                "type": "auth",
                "access_token": os.environ["HA_TOKEN"]
            }))

            auth = json.loads(ws.recv())
            if auth.get("type") != "auth_ok":
                raise RuntimeError("Home Assistant authentication failed")

            ws.send(json.dumps({
                "id": 1,
                "type": "media_player/browse_media",
                "entity_id": self.entity_id,
                "media_content_type": "game",
                "media_content_id": "Game"
            }))

            response = json.loads(ws.recv())

            if not response.get("success"):
                raise RuntimeError(f"Browse failed: {response}")

            return [
                {
                    "name": game["title"],
                    "id": game["media_content_id"],
                    "type": game["media_content_type"]
                }
                for game in response["result"].get("children", [])
                if game.get("can_play")
            ]

        finally:
            ws.close()

    def launch_game(self, game_name):
        """Find an installed game by name and launch it."""
        games = self.get_installed_games()

        def normalize(name):
            return "".join(
                char.lower() for char in name if char.isalnum()
            )

        query = normalize(game_name)

        # Prefer exact matches
        matches = [
            game for game in games
            if normalize(game["name"]) == query
        ]

        # Allow partial matches if no exact match exists
        if not matches:
            matches = [
                game for game in games
                if query in normalize(game["name"])
            ]

        if not matches:
            available = ", ".join(game["name"] for game in games)
            raise ValueError(
                f"Game '{game_name}' not installed. "
                f"Available: {available}"
            )

        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous game name: {game_name}. "
                f"Matches: {[g['name'] for g in matches]}"
            )

        game = matches[0]

        self._call_service("play_media", {
            "media_content_id": game["id"],
            "media_content_type": game["type"]
        })

        return game["name"]


    def turn_on(self):
        return self._call_service("turn_on")

    def turn_off(self):
        return self._call_service("turn_off")
