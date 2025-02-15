# MSPMeshBot
A [Red-DiscordBot Cog](https://docs.discord.red/en/latest/index.html) for browsing Meshtastic Node data stored in Google Sheets, submitted in Google Forms

![image](https://github.com/user-attachments/assets/c8e2f147-6b3c-474c-a26a-cbdaf8567f36)

**What is this?**
This is a Cog for allowing your regional Meshtastic group to organize their nodes and allow other users to query who owns nodes they find along the mesh in real life.
Drastically reduce the amount of "Who has this node?" questions in your chats and create a central directory of your infrastructure to determine quiet zones and fill out gaps.

# Requirements

* A Google Account
* Google Cloud Access (For Sheets API. This can entirely be done on the Free tier.)
* A Discord Account.
* Access to the [Discord Developer Portal] (https://discord.com/developers/applications).
* A server capable of running Python 3.11.x, or higher, or possibly slightly lower.
* Some setup time.

# Installation

## Google Installation

1) With your Google Account, head over to the [Example Google Form](https://drive.google.com/drive/folders/14CoK4XRR_SexdnPJ2oq6Efpij5ewz1RB?usp=sharing) and Make A Copy to your own Google Drive.
2) RENAME the Form to a unique form name.
3) Go to Responses and create a new Google Sheet to link the responses to.
4) RENAME the Responses Sheet to whatever works best.
5) Head to Google Cloud, create a new project and enable the Sheets API.
6) Create a Service User, create a new key, download the JSON file. Rename to `credentials.json` and keep handy.
7) Write down the Sheets ID (https://docs.google.com/spreadsheets/d/[a bunch of stuff you want to copy]/edit?gid=a bunch of stuff nobody cares about#gid=more trash forget this stuff)
8) Write down the Responses Sheet Name.

## Discord Installation

1) Go to the Developer Portal and create a new Application, ensure it's a Bot, and write down the Secret.
2) Add a funny picture, ensuring it doesn't violate the Meshtastic trademarks.

## Server Installation

1) Follow the Red-DiscordBot installation instructions.
2) Add the mesh_nodes.py file from this repo into your Cogs folder.
3) Ensure your !paths are pointing to a directory you can put the repo files in.
4) Load the Github file `mesh_nodes.py` into your Mesh Cog directory.
5) Move your downloaded `credentials.json` file as well.
6) Run `!load mesh_nodes`, then fill out the config file. Here is where you'll put your Sheet Name and Sheet ID.
7) Reload with `!reload mesh_nodes`.
8) ???
9) Profit!

##Github Installation

Now that you've struggled through my terrible directions, make a PR with slightly better ones.
