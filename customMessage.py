import re
import os
import sys
import json
import ctypes
import webview
import requests
import websocket
from threading import Thread
from firebase import firebase

try:
    url = "https://www.yapdollar.com/chatbox.html"
    agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
    header = {"User-Agent": agent}
    js = requests.get(url, header).text.split('// ')[1]
except Exception as e:
    sys.exit(e)

# global variables & constants
ver = 5
internalHost = 's-usc1f-nss-2546.firebaseio.com' # update to 2547
configs = re.findall(r"\"[\S.]+\"", js)
db = configs[2][1:-1] # https://yapdollar-chat-default-rtdb.firebaseio.com
appId = configs[6][1:-1] # 1:268472109374:web:1c538b25d9eba4b8af846f
ns = db.split('//')[1].split('.')[0] # yapdollar-chat-default-rtdb

wss = str(f'wss://{internalHost}/.ws?v={ver}&p={appId}&ns={ns}') # normally, would call firebase SDK file for websocket uri

logging = False # mainly for debugging
firstLaunch = True

profiles = []
activeProfile = {}
template = {
        "profiles": profiles,
        "activeProfile": activeProfile
    }
profileCfgPath = os.curdir
profileCfgName = "ProfileData.json"
profileCfgLocation = os.path.join(profileCfgPath, profileCfgName)

if not os.path.exists(profileCfgLocation):
    with open(profileCfgLocation, 'x') as create:
        json.dump(obj=template, fp=create)
with open(profileCfgLocation, 'r') as Config:
    Data = json.load(Config)
    profiles = list(Data['profiles'])
    activeProfile = Data['activeProfile']

title = "Yap Dollar Chatbox"
credit = "kxso.xyz"

# buttons
MB_OK = 0x0
MB_OKCXL = 0x01
MB_YESNOCXL = 0x03
MB_YESNO = 0x04
MB_HELP = 0x4000

# icons
ICON_EXCLAIM = 0x30
ICON_INFO = 0x40
ICON_STOP = 0x10

# response codes
RC_YES = 6
RC_NO = 7

hue = {
    "yellow": ["[33;33m", "#C19C03"],
    "cyan": ["[38;5;51m", "#04FFFF"],
    "pink": ["[38;5;219m", "#faa1ff"],
    "red": ["[40;31m", "#C50F1F"],
    "green": ["[40;32m", "#108C0E"],
    "blue": ["[40;34m", "#0B24BC"],
    "rosa": ["[40;91m", "#E74856"],
    "lime": ["[40;92m", "#16C60C"],
    "sky": ["[40;94m", "#3B78B8"]
}
reset = "[00m" # white by default
colors = f"{f'{reset}, '.join(str(hue[color][0] + color) for color in list(hue)[:-1])}{reset}, or {hue[list(hue)[-1]][0] + list(hue)[-1]}{reset}"

def Mbox(title, text, style):
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)

def Title(status=""):
    text = ""
    if (status != ""):
        text += f"  |  {status}"
    return ctypes.windll.kernel32.SetConsoleTitleW(title + text)

class chat:
    def saveProfile():
        profileCfg = os.path.exists(profileCfgLocation)
        if (profileCfg):
            with open(profileCfgLocation, 'w') as config:
                json.dump(obj=template, fp=config)
        return profileCfg

    def getColor(hexcolor):
        for label in hue:
            if (hue[label][1] == hexcolor):
                return hue[label][0] # bad practice to return inside loop

    def setup(reason=None):
        profile = {
            "name": "",
            "color": ""
        }
        setupStatus = False

        try:
            Title("Creating profile")
            profileExists = bool(len(profiles) > 0)
            if (profileExists):
                choice = int(Mbox(title, "You already have a profile.\nWant to create a new one?", MB_YESNO)) # yes: 6, no: 7
                if (choice == RC_YES):
                    reason = None
                if (choice == RC_NO):
                    setupStatus = True
                    return setupStatus
            elif (reason != None):
                Mbox(title, f"{reason}\nCreate a new profile.", ICON_STOP)
            
            name = input("Create a username: ")
            if (name != ""):
                if (name.isalpha()):
                    profile["name"] = name
                else:
                    Mbox(title, "Username must only contain letters.", ICON_EXCLAIM)
                    return setupStatus
            else:
                Mbox(title, "Username cannot be empty.", ICON_STOP)
                return setupStatus
            print(f"Username can be {colors}.")
            color = input("Pick a color: ")
            if (color in hue):
                profile["color"] = hue[color][1]
            else:
                Mbox(title, "Please choose from one of the listed colors.", ICON_STOP)
                return setupStatus
            newProfile = hue[color][0] + name + reset
            profiles.append(profile)
            chat.saveProfile()
            print(f"Profile {newProfile} has been created.")
            setupStatus = True
            client()
            return setupStatus
        except KeyboardInterrupt as KI:
            sys.exit(KI)
        except Exception as e:
            Mbox(title, e, ICON_STOP)

    def switchProfile(profile=None):
        global activeProfile, profiles
        try:
            Title("Switching profiles")
            profileExists = bool(len(profiles) > 0)
            profileFound = False
            switchStatus = False

            if (profile is not None):
                if (profileExists):
                    for sets in profiles:
                        if (profile == sets["name"]):
                            profileFound = True
                            for index, key in enumerate(profiles):
                                if (key["name"] == profile):
                                    color = chat.getColor(key["color"])
                                    savedProfile = color + profile + reset
                                    activeProfile = profiles[index]
                                    template['activeProfile'] = profiles[index]
                                    chat.saveProfile() # bug: deletes saved profiles
                                    print(f"Profile switched to {savedProfile}.")
                                    switchStatus = True
                    if (not profileFound):
                        Mbox(title, f"Couldn't find profile {profile}.", ICON_EXCLAIM) # currently bugged
                else:
                    chat.setup("No profiles found.")
            else:
                Mbox(title, "Profile was not declared.", ICON_STOP)
            return switchStatus
        except KeyboardInterrupt as KI:
            sys.exit(KI)
        except Exception as e:
            sys.exit(e)

class ext: # dedicated to pywebview functions
    chatbox = webview.create_window(title=title, url=url, background_color='#000000')
    isClosed = False

    def injectJs(window):
        javascript = "document.getElementById('chat-input').remove();"
        css = """* {scrollbar-color: #282f34 #000000}
        html, body {background-color: rgb(0, 0, 0);}
        #chat-messages {border-color: rgb(29, 38, 41); background-color: rgb(0, 0, 0);}
        #chat-messages {flex: 1; overflow-y: auto; border: 1px solid #faa1ff; padding: 10px; border-radius: 3px; margin-bottom: 10px;}
        span.text {color: #ffffff;}
        #chat-input input {border-color: #faa1ff;}
        #chat-input button {background-color: #faa1ff; color: #000000; border-width: initial; border-style: none; border-color: initial;}
        #chat-input button:hover {background-color: #f483f4; color: rgb(255, 255, 255)}"""
        window.on_top = False
        window.evaluate_js(javascript) # deletes textbox element
        window.load_css(css) # custom dark theme
        
        #jsi = window.evaluate_js("document.getElementById('message-input').remove(); var sendButton = document.getElementById('send-button'); sendButton.innerHTML = 'Send Message'; sendButton.addEventListener('click', function () {'Sent pressed';});")
        #print(jsi)
        #window.evaluate_js("enUsr = document.createElement('div'); enUsr.id = 'user-input'; enUsr.style.border = '1px solid #faa1ff'; enUsr.innerHTML += document.getElementById('message-input').outerHTML + document.getElementById('send-button').outerHTML; document.getElementById('chatbox-container').appendChild(enUsr);")
        return

    def wv(): # opens WebView window
        try:
            Title("Opening WebView")
            webview.start(ext.injectJs, ext.chatbox)
        except Exception as e:
            sys.exit(e)

    def Window(suffix=None):
        print(ext.chatbox.minimized)
        if ext.chatbox.hidden:
            print("Opening external chatbox window")
            ext.chatbox.restore()
        elif (ext.chatbox.minimized):
            print("Opening external chatbox window 1")
            ext.chatbox.show()
        elif (ext.chatbox.minimized): # change to check if win closed
            print("Opening external chatbox window 1")
            ext.chatbox.show()
        else:
            print("Closing external chatbox window")
            #ext.chatbox.destroy()
            ext.chatbox.hide()
    
class cmd:
    def glossary():
        Title("Commands")
        color = chat.getColor(activeProfile['color'])
        for dicts in cmd.commands:
            cmdKey = list(dicts.keys())[0]
            cmdValue = dicts[cmdKey][0]
            print(f"{color}{cmdKey}{reset}\n– {cmdValue}")

    def close(code=None):
        Title("Closing chatbox")
        sys.exit(code)

    # example command arguments
    exSearchArg = 'yapdollar'
    exDeleteArg = '-OHATZE74sjHD36n0WyS'
    exProfileArg = 'profilename'

    commands = [
        # cmds     description                            executes
        {"help": ['Displays a list of helpful commands.', glossary]},
        {"switch": [f'Switches current profile to the\n  selected alternative.\n  eg. "$switch {exProfileArg}"', chat.switchProfile]},
        {"create": ['Propts user to create a new profile.', chat.setup]},
        {"remove": [f'Removes selected profile (cannot be undone).\n  eg. "$remove {exProfileArg}"', None]},
        {"stats": ['Displays stats for remote server.', None]}, # add ping
        {"window": ['Closes/opens external chatbox window.', ext.Window]},
        {"search": [f'Returns a list comprised of IDs\n  where messages matched the input\n  search value.\n  eg. "$search {exSearchArg}"', None]},
        {"delete": [f'Deletes selected message by ID.\n  eg. "$delete {exDeleteArg}"', None]},
        {"update": ['Checks for updates. Restarts when finished.', None]},
        {"exit": ['Exits terminal. Closes all windows.', close]},
        {"ping": ['Pings server.', None]},
        {"clear": ['Erases local chatlogs, creating a\n  fresh slate to send messages.', None]},
        {"users": ['Shows all contemporary saved profiles.', None]},
        {"info": [f'Displays information relating to the\n  development of {title}.', None]},
        {"version": ['Returns version info.', None]}
    ]

    def breakout(raw):
        try:
            cmdStatus = False
            arg = None
            rawCmd = raw.split(' ')
            command = rawCmd[0]
            if command.isalpha():
                command = command.lower()
                if (len(rawCmd) > 1):
                    arg = rawCmd[1]
                for dicts in cmd.commands:
                    if (command in dicts):
                        exe = dicts[command][1]
                        if (exe is not None):
                            if (arg is not None):
                                exe(arg)
                            else:
                                exe()
                            cmdStatus = True
                        else:
                            print("Cannot execute command at this time.")
                if (not cmdStatus):
                    print(f'Command "{command}" not found.')
            else:
                print("Invalid input.")
            return cmdStatus
        except Exception as e:
            sys.exit(e)

'''
class database:
    try:
        fb = firebase.FirebaseApplication(db, None) # apikey: 'AIzaSyB-tCk1TO8u94PYjVhBqACr5sYnT_nl8Pk'
        key = str(json.loads(json.dumps(fb.post('/messages', None)))["name"]) # database.ref().child('messages').push().key;
        num = len(json.loads(json.dumps(fb.get('/messages', None)))) # number of messageKeys in database
    except Exception as e:
        Mbox(title, e, ICON_EXCLAIM) # change later for GUi
'''
''' much too resource-intensive of a task
stats = f"""
Server Version: {ver}
Messages sent: {database.num:,}
Project: {ns}
Current Color Index: {len(hue)}
Development: {credit}
""" # calling database function causes slight lag in performance
'''

def initConnection(uri):
    try:
        Title("Connecting to wss")
        websocket.enableTrace(logging)
        ws = websocket.create_connection(uri)
        ws.connect(uri, headers=header) # redundant?

        if (ws.connected):
            response = ws.recv()
            endpoint = str(json.loads(response.split('\n')[0])['d']['d']['h']) # host key: {'t': 'c', 'd': {'t': 'h', 'd': {'ts': 1737102360753, 'v': '5', 'h': 's-usc1f-nss-2547.firebaseio.com', 's': 'kVDb2zofN28HHquzPaqfxMYl2x2giYAX'}}}
            DNS = uri.split('/', 3)[2] # parses wss var for domain
            if (endpoint == DNS):
                Title("Connection established")
            else:
                Title("Connection incomplete")
        else:
            Title("Connection failed")
            Mbox(title, "Could not connect to Websocket server.\nMake sure to have an active network connection.", ICON_STOP)

        return ws
    except websocket._exceptions.WebSocketConnectionClosedException as WSCCE:
        sys.exit(WSCCE)
    except Exception as e:
        sys.exit(e)

def sendMessage(text):
    userId = activeProfile['name']
    color = activeProfile['color']

    try:
        Title("Connecting to db")
        database = firebase.FirebaseApplication(db, None) # apikey: 'AIzaSyB-tCk1TO8u94PYjVhBqACr5sYnT_nl8Pk'
        newMessageKey = str(json.loads(json.dumps(database.post('/messages', None)))["name"]) # database.ref().child('messages').push().key;
    except Exception as e:
        Mbox(title, e, ICON_EXCLAIM)
        sys.exit(e)

    message = json.dumps({
    "t": "d",
    "d": {
        "r": 4,
        "a": "m",
        "b": {
            "p": "/",
            "d": {
                f"/messages/{newMessageKey}": {
                "text": text,
                "timestamp": {
                    ".sv": "timestamp"
                },
                "userId": userId,
                "color": color
                }
            }
        }
    }
    }).encode('utf-8') # .sv = ServerValue

    try:
        Title("Sending message")
        ws = initConnection(wss) # initialize connection to websocket server

        ws.send(message)

        if (ws.connected):
            response = ws.recv()
            status = json.loads(response.split('\n')[0])["d"]["b"] # response status: {"t":"d","d":{"r":9,"b":{"s":"ok","d":""}}}

        messageStatus = ""
        if (status["s"] == "ok"):
            messageStatus = "Message sent"
        else:
            messageStatus = status["d"] # data

        ws.close(ws.status)

        return messageStatus
    except KeyboardInterrupt as KI:
        sys.exit(KI)
    except websocket._exceptions.WebSocketConnectionClosedException as WSCCE:
        sys.exit(WSCCE)
    except Exception as e:
        sys.exit(e)

def client():
    try:
        savedProfiles = profiles
        profileExists = bool(len(savedProfiles) > 0)

        os.system('chcp 65001 >nul') # io utf-8 encoding
        os.system('mode 54,40 >nul') # (width, height*2)
        #os.system('mode 41,40 >nul')
        Title()

        if (not profileExists):
            createProfile = chat.setup(None)
            if (not createProfile):
                chat.setup(None)
            return
        else:
            #if (firstLaunch): # first launch verification
            if (activeProfile == {}): # auto-login if active profile isn't empty
                Title("Picking profile") # move to switch function

                if (len(savedProfiles) > 1):
                    s = "s"
                    users = f"{f'{reset}, '.join(str(chat.getColor(dict(inst)['color']) + dict(inst)['name']) for inst in list(savedProfiles)[:-1])}{reset}, and {chat.getColor(dict(list(savedProfiles)[-1])['color']) + dict(list(savedProfiles)[-1])['name']}{reset}"
                else:
                    s = ""
                    users = chat.getColor(savedProfiles[0]['color']) + savedProfiles[0]['name'] + reset
                print(f"Choose from saved profile{s} {users}.")

                validProfile = chat.switchProfile(input("Select profile: "))
                if (not validProfile):
                    client()
                    return
            Title("Profile loaded")

            color = chat.getColor(activeProfile['color'])
            print(f"Connected as {color}{activeProfile['name']}{reset}.")
            
            #stats += f"""Profile: {chat.activeProfile['name']}"""
            print("(type $help for a list of commands)")
            print("Start yapping!")
            while profileExists: # (True)
                message = input("")
                if (message != ""):
                    if (len(message) < 250):
                        if (message.startswith("$")):
                            command = message.split("$")[1]
                            sendCommand = cmd.breakout(command)
                            if (sendCommand):
                                Title("Command success")
                            else:
                                Title("Command failed")
                            input("Press any key to go back.")
                            break
                        else:
                            response = sendMessage(message)
                            Title(response)
                            print(f"{color}{activeProfile['name']}:{reset} {message}")
                    else:
                        print("Message exceeds max character limit.")
            client()
        return
    except KeyboardInterrupt as KI:
        sys.exit(KI)
    except Exception as e:
        sys.exit(e)

def main():
    try:
        # TODO:
        # display server data via requests and db
        # write command key on initialization for breakout codes (read below)
        # add message breakout codes assigned to functions like switching profiles or creating new ones
        # create breakout closing and opening messages WebView windows
        # save profiles on local system rather than as a variable in memory

        Thread(target = client, daemon = True).start() # https://stackoverflow.com/a/51723355
        ext.wv() # has to be on main Thread

        return
    except KeyboardInterrupt as KI:
        sys.exit(KI)
    except AttributeError as AE:
        sys.exit(AE)
    except Exception as e:
        sys.exit(e)

main()
