
from agent.controller import XboxController

xbox = XboxController()

print("Turning on Xbox...")
xbox.turn_on()

print("Waiting for Xbox...")
xbox.wait_until_ready()

print("\nInstalled games:")
for game in xbox.get_installed_games():
    print(f" - {game['name']}")

game_name = input("\nWhich game would you like to launch? ")

print(f"\nLaunching {game_name}...")
launched = xbox.launch_game(game_name)

print(f"Launch command sent for {launched}!")
