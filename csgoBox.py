#!/usr/bin/python


############################################################
#
#  CS:GO light 
#
#  Joe Sciarappa
#
#
############################################################

import sys
from Adafruit_CharLCD import Adafruit_CharLCD
from lcdScroll import Scroller
import RPi.GPIO as GPIO
import time
import thread 
from Queue import Queue, Empty
from threading import Thread
import atexit
import mysql.connector as mariadb
import json
import requests
import random 
from subprocess import call
import logging

###### Initialize GPIO
#GPIO Mode
GPIO.setmode(GPIO.BCM)
#Disable Warnings
GPIO.setwarnings(False)
#Blue LED 
GPIO.setup(16, GPIO.OUT)
#Red LED
GPIO.setup(17, GPIO.OUT)
#Green LED
GPIO.setup(18, GPIO.OUT)
#Switch
GPIO.setup(21,GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
########################
###### Initialize LCD
lcd = Adafruit_CharLCD(rs=26, en=19,d4=13, d5=6, d6=5, d7=11,cols=16, lines=1)
lcd.clear()
########################
###### Queues
#LED queue
led_queue = Queue(maxsize=35)
#LCD Queue
lcd_queue = Queue(maxsize=20)
#Queue List
qlist=[led_queue, lcd_queue]
########################
UserIDs=['76561198048899886', '76561197995382883', '76561198036278488', '76561197977936526']


########################
###### Logging
logger = logging.getLogger('CS:GO Box')
hdlr = logging.FileHandler('/var/log/csgo.log')
formatter = logging.Formatter('%(asctime)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
##Set logging Level
#Options include: CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET
logger.setLevel(logging.DEBUG)
logger.critical("CS:GO Box starting")
########################
importantMessage=0



#### MySQL Functions ####
def switch_table(state):
	mariadb_connection = mariadb.connect(user='csgo', password='ZWU1MDk1ZDExY2M', database='csgo')
	cursor = mariadb_connection.cursor(dictionary=True)
	cursor.execute('''INSERT INTO switch (switch) VALUES (%s)''' %(state))
	mariadb_connection.commit()
	mariadb_connection.close()

def status_table(status):
	mariadb_connection = mariadb.connect(user='csgo', password='ZWU1MDk1ZDExY2M', database='csgo')
        cursor = mariadb_connection.cursor(dictionary=True)	
	cursor.execute('''SELECT status FROM steam_status WHERE code = "%s"''' %(status))
        status = cursor.fetchone()['status']

        mariadb_connection.close()
	return status
def id_table(SteamID):
        mariadb_connection = mariadb.connect(user='csgo', password='ZWU1MDk1ZDExY2M', database='csgo')
        cursor = mariadb_connection.cursor(dictionary=True)
        cursor.execute('''SELECT username FROM steam_ids WHERE id = %s''' %(SteamID))
        username = cursor.fetchone()['username']
        mariadb_connection.close()
        return username

#### Firebase Integration ####

def firebaseGET():
	global importantMessage
	url = 'https://csgo-light.firebaseio.com/.json'
	on_previous = 0
	on_now = 0
	while True:
		try:
	                if int(time.time()) % 2 == 0: 
				ondevices=''	
				r = requests.get(url)
				for device in r.json()["devices"]:
				        if device != 'Joe' and r.json()["devices"][device]["lightStatus"] == 1:
						on_now += 1
						ondevices += device
				logger.debug("lights on: " + str(on_now))
				logger.debug("Important Message: " + str(importantMessage))
				if on_previous != on_now and on_now > 0:
					importantMessage=1
					logger.info("Light On! " + str(ondevices))
					lightOnthread = Thread(target=lightOn, args = (ondevices,))
					lightOnthread.start()
				elif on_previous != on_now and on_now == 0:
					importantMessage=0
					logger.info("Light Off!")
		        		lcd_queue.put( ["All devices", ["Inactive"], -1] )

				on_previous=on_now
				on_now=0	
			time.sleep(.5)
		except ValueError:
			pass
			

def firebasePUT(state):
	csgoLightServer = 'https://csgo-light.firebaseio.com/devices/Joe.json'
	etime = int(time.time())	
	requests.put(csgoLightServer, json={"lightStatus": state, "Time changed": etime}).json()

#### Steam API ####

def steamAPIstatus(UserIDs):
	global importantMessage
	while True:
		try:
			if (int(time.time()) % 1200) % 43 == 0 and importantMessage == 0:
				url = 'http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=9CA18501EEF1C3007C16222189EC66F8&steamids='
				for i in UserIDs:
					url += i + ','
				r = requests.get(url)
				for i in range(len(r.json()["response"]["players"])):
					username = r.json()["response"]["players"][i]["personaname"]
					try:
						state = "In Game: " + r.json()["response"]["players"][i]["gameextrainfo"]
					except KeyError:
						state = status_table(r.json()["response"]["players"][i]["personastate"])
					lcd_queue.put([username, [state], 2])
					logger.info([username, [state], 2])
			time.sleep(.9)
		except ValueError:
			pass

def steamAPIinGame(UserIDs):
	global importantMessage
	ingame = 0
	while True:
		try:
	                if ((int(time.time()) % 1200) % 17) == 0:
        	                url = 'http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=9CA18501EEF1C3007C16222189EC66F8&steamids='
	                        for i in UserIDs:
        	                        url += i + ','
                	        r = requests.get(url)
	                        if "gameextrainfo" in str(r.json()['response']['players']):
        	                        lcd_killandclear()
                	                for i in range(len(r.json()["response"]["players"])):
	                                        username = r.json()["response"]["players"][i]["personaname"]
        	                                try:
                	                                state = "In Game: " + r.json()["response"]["players"][i]["gameextrainfo"]
	                                        except KeyError:
        	                                        state = status_table(r.json()["response"]["players"][i]["personastate"])
                	                        if "In Game:" in state:
	                                                lcd_queue.put([username, [state], 1])
        	                                        led_queue.put( [blue_led, 6] )
                	                                importantMessage = 1
                        	                        ingame = 1
	                                                logger.info([username, [state], 1])
        	                else:
                	                logger.debug("No one in game")
                        	        if ingame == 1 and importantMessage == 1:
                                	        ingame = 0
                                        	importantMessage = 0
	
			time.sleep(1.1)
		except ValueError:
			pass

def steamAPIstats(UserIDs):
	global importantMessage
	while True:
		try:
	                if ((int(time.time()) % 1200) % 157) == 0 and importantMessage == 0:
				statArray=[]
                	        for i in UserIDs:
                        	        statList=[]
                                	username = id_table(i)
	                                url='http://api.steampowered.com/ISteamUserStats/GetUserStatsForGame/v0002/?appid=730&key=9CA18501EEF1C3007C16222189EC66F8&steamid='
        	                        url+=i
                	                r = requests.get(url)
                        	        PlayerStatsDict={}
                                	for j in range(len(r.json()["playerstats"]["stats"])):
	                                        if "GI.lesson" not in r.json()["playerstats"]["stats"][j]["name"] and "gg_contribution" not in r.json()["playerstats"]["stats"][j]["name"]:
        	                                        PlayerStatsDict.update({r.json()["playerstats"]["stats"][j]["name"].replace("_", " ") : r.json()["playerstats"]["stats"][j]["value"]})
                	                for k in range(2):
                        	                statKey = random.choice(PlayerStatsDict.keys())
                                	        statString = statKey + ' : ' + str(PlayerStatsDict[statKey])
                                        	statList.append(statString)
					statArray.append([username, statList, 1])
	
				for i in range(len(statArray)):
					lcd_queue.put(statArray[i])
					logger.info(statArray[i])
			time.sleep(1.1)
		except ValueError:
			pass

def steamAPIrecent(UserIDs):
	global importantMessage
	while True:
		try:
	                if (int(time.time()) % 1200) % 1193 == 0 and importantMessage == 0:
        	                for i in UserIDs:
                	                username = id_table(i)
					logger.debug("getting " + username + " recents")
	                                url='http://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/?key=9CA18501EEF1C3007C16222189EC66F8&steamid='
        	                        url+=i
                	                r = requests.get(url)
	                                game_string = ['Recently Played: ' + r.json()["response"]["games"][0]["name"][:14]  , 'Playtime 2 Weeks: ' + str(round(r.json()["response"]["games"][0]["playtime_2weeks"] / float(60),1)), 'Playtime Total: ' + str(round(r.json()["response"]["games"][0]["playtime_forever"] / float(60),1)) ]
        	                        lcd_queue.put([username, game_string, 1])
                	                logger.info([username, game_string, 1])
				time.sleep(5)

			time.sleep(1.1)
		except ValueError:
			pass
#### Hardware ####

def lightOn(device):
	led_queue.put( [red_led, 21] )
	lcd_killandclear()
        lcd_queue.put( [device, ["Active"], -1] )
	logger.info([device + " Switch", ["Active"], -1] )
	call(["/usr/bin/omxplayer", "--vol", "1200", "/home/csgo/audio/ready.mp3" ])


def switch():
	count = 0
	on = 0
	while count <= 5:
		if (GPIO.input(21)):
			on += 1
		else:
			on -= 1

		time.sleep(.025)
		count+=1
   
	if on > 0:
		return True 
	else:
		return False

def blue_led(iterate):
        for x in range(0,iterate):
                GPIO.output(16,GPIO.HIGH)
                time.sleep(.4)
                GPIO.output(16,GPIO.LOW)
                time.sleep(.4)

def red_led(iterate):
	for x in range(0,iterate):
		GPIO.output(17,GPIO.HIGH)
		time.sleep(.4)
		GPIO.output(17,GPIO.LOW)
		time.sleep(.4)	

def green_led(iterate):
        for x in range(0,iterate):
                GPIO.output(18,GPIO.HIGH)
                time.sleep(.4)
                GPIO.output(18,GPIO.LOW)
                time.sleep(.4)

def debug_print(array):
	print array


def lcd_print(queue):
	while True:
		payload=queue.get()
		for i in range(len(payload[1])):
			if len(payload[0]) < 16:
				space = (16 - len(payload[0])) / 2
				payload[0] = ' '*space + payload[0] + ' '*space
			elif len(payload[0]) > 16:
				payload[0] = payload[0][:16]

			if len(payload[1][i]) < 16:
				space = (16 - len(payload[1][0])) /2 
				payload[1][0] = ' '*space + payload[1][0] 	
			elif len(payload[1][i]) > 16:
				payload[1][i] = ' ' + payload[1][i]
				
	
		        lines = [payload[0] , payload[1][i]]
 		        message="\n".join(lines)	

			if len(payload[1][i]) <= 16:
				lcd.clear()	
			        lcd.message(message)
				time.sleep(1.5)
			else:	
	        		for j in range(len(payload[1][i]) - 16):
		                        scroller = Scroller(lines=lines)
					message = scroller.scroll()
					lcd.clear()
					lcd.message(message)
					if j == 0:
						time.sleep(1.5)
					if j == (len(payload[1][i]) - 17):	
						time.sleep(1.1)
                			time.sleep(.9)
			if payload[2] != -1:
				time.sleep(payload[2])
				lcd.clear() 

def led(queue):
	while True:
		items = queue.get()
		f = items[0]
		p = items[1:]
		f(*p)
		queue.task_done()


#### Clean Up 		
def cleanup(queue):
	logger.critical("CS:GO Box exiting")
	for queue in qlist:
		with queue.mutex:
			queue.queue.clear()

	lcd.clear()
	GPIO.cleanup()  

def lcd_killandclear():
        with lcd_queue.mutex:
                lcd_queue.queue.clear()


######## Main Function ########

def main():

	###### Queue & Threads
	#LED Queue Thread
	ledthread = Thread(target=led, args=(led_queue,))
	ledthread.setDaemon(True)
	ledthread.start()
	#LCD Queue Thread
        lcdthread = Thread(target=lcd_print, args=(lcd_queue,))
        lcdthread.setDaemon(True)
        lcdthread.start()
	#Steam Threads
	steamAPIstatusThread = Thread(target=steamAPIstatus, args=(UserIDs,))
	steamAPIstatusThread.setDaemon(True)
	steamAPIstatusThread.start()

	steamAPIinGameThread = Thread(target=steamAPIinGame, args=(UserIDs,))
	steamAPIinGameThread.setDaemon(True)
	steamAPIinGameThread.start()

	steamAPIstatsThread = Thread(target=steamAPIstats, args=(UserIDs,))
	steamAPIstatsThread.setDaemon(True)
	steamAPIstatsThread.start()

	steamAPIrecentThread = Thread(target=steamAPIrecent, args=(UserIDs,))
	steamAPIrecentThread.setDaemon(True)
	steamAPIrecentThread.start()


	########################
	#Firebase Thread
        firebasethread = Thread(target=firebaseGET)
        firebasethread.setDaemon(True)
        firebasethread.start()



	###### Cleanup
	atexit.register(cleanup, qlist)
	########################


	###### Initial Variables
	switch_last = switch()	
	global importantMessage 
 
	while True: 

		switch_now = switch()	

		if switch_now != switch_last and switch_now:	
			importantMessage = 1
			logger.info("importantMessage: " + str(importantMessage))
			led_queue.put( [green_led, 1] )
			led_queue.put( [blue_led, 1])
			lcd_killandclear()
                        lcd_queue.put( ["CS:GO Switch", ["Active"], -1] )
			logger.info(["CS:GO Switch", ["Active"], -1] )
			firebasePUT(1)
			call(["/usr/bin/omxplayer", "/home/csgo/audio/lets_roll.wav" ])
			switch_table(1)

		elif switch_now != switch_last and not switch_now:	
			importantMessage = 0
			logger.info("importantMessage: " + str(importantMessage))
			led_queue.put( [green_led, 1] )
			led_queue.put( [blue_led, 1] )
			lcd_killandclear()	
			lcd_queue.put( ["CS:GO Switch", ["Inactive"], -1] )
			logger.info(["CS:GO Switch", ["Inactive"], -1] )
			firebasePUT(0)
			switch_table(0)
		

		switch_last = switch_now	

if __name__ == "__main__":
    main()
