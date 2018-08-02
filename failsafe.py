#!/usr/bin/python2.7

import ping, os, time, socket, threading

class failsafe_and_stuff:

  def __init__(self,base_ip="10.0.0.2",ping_timeout=8, ping_delay=2, cmd_delay=3,cmd_udp_port=12357,debug=False):
    self.base_ip = base_ip
    self.connected = False
    self.udp_connected = False
    self.ping_delay = ping_delay
    self.cmd_delay = cmd_delay
    self.ping_timeout = ping_timeout
    self.safe_exit = False
    self.threads = []
    self.cmd_udp_port = cmd_udp_port
    self.debugging = debug
    self.wait_for_connection()

  def debug(self,m):
    if self.debugging:
      print m

  def add_thread_and_start(self,t):
    self.threads.append(t)
    t.start()

  def wait_for_connection(self):
    self.debug("Waiting for connection to %s" % self.base_ip)
    self.add_thread_and_start(threading.Thread(target=self.udp_listener))

    while not self.connected:
      if ping.do_one(self.base_ip,2) != None:
        self.connected = True
    self.debug("Connected to %s" % self.base_ip)
    self.add_thread_and_start(threading.Thread(target=self.ping_failsafe))
    
    self.udp_failsafe()
    self.debug("finishing up")
    for thread in self.threads:
      thread.join() 

    self.debug("done") 
  def ping_failsafe(self):
    if self.ping_timeout != -1:
      while not self.safe_exit:
        if ping.do_one(self.base_ip,self.ping_timeout) != None:
          time.sleep(self.ping_delay)
        else: 
          self.trigger_failsafe(source="ping")

  def trigger_failsafe(self,source=""):
    self.debug("failsafe activated %s" % source)
    os.system("reboot")
    
  def trigger_deauth(self):
    self.debug("deauth activated")
    os.system("ps -ef | egrep deauth.s[h] | egrep -v grep || bash deauth.sh")

  def trigger_nc_dump_cam(self):
    self.debug("killing raspivid and relaunching piped to nc")
    os.system("pkill raspivid; ( /opt/vc/bin/raspivid -t 0 -w 640 -h 480 -hf -fps 15 -o - | tee /home/pi/dev/logs/camera_dump_$(date | sed -e 's/ /_/g') | socat - UDP-DATAGRAM:10.0.0.2:5600,sourceport=5600 ) &")
  
  def trigger_nc_cam(self):
    self.debug("killing raspivid and relaunching piped to nc")
    os.system("pkill raspivid; ( /opt/vc/bin/raspivid -t 0 -w 640 -h 480 -hf -fps 15 -o - | socat - UDP-DATAGRAM:10.0.0.2:5600,sourceport=5600 ) &")
#nc -l -p 5600 -u | tee capsave.test | mplayer -fps 200 -demuxer h264es -

  def trigger_qgc_cam(self):
    self.debug("killing raspivid and relaunching piped to gstreamer")
    os.system("pkill raspivid; /home/pi/dev/camera.sh")
#gst-launch-1.0 -e -v udpsrc port=5600 ! application/x-rtp,clock-rate=90000,payload=96 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert !  autovideosink

  def kill_cam(self):
    self.debug("stopping raspivid")
    os.system("pkill raspivid")

  def udp_listener(self):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0",self.cmd_udp_port))
    while not self.safe_exit:
      data, addr = sock.recvfrom(1)
      if addr[0] == self.base_ip:
        self.last_udp_heartbeat = time.time()
      if data == "A":
	if self.udp_connected == False:
	  print "starting udp failsafe watcher"
        self.udp_connected = True
        self.connnected = True
        pass #alive
      elif data == "K":
        self.add_thread_and_start(threading.Thread(target=self.trigger_failsafe)) # kill
      elif data == "D":
        self.add_thread_and_start(threading.Thread(target=self.trigger_deauth)) # deauth
      elif data == "C":
        self.add_thread_and_start(threading.Thread(target=self.trigger_qgc_cam)) # kill camera and launch raw nc over udp
      elif data == "B":
        self.add_thread_and_start(threading.Thread(target=self.kill_cam)) #disable camera
      elif data == "M":
        self.add_thread_and_start(threading.Thread(target=self.trigger_nc_dump_cam)) # kill camera and launch raw nc over udp after saving to disk
      elif data == "N":
        self.add_thread_and_start(threading.Thread(target=self.trigger_nc_cam)) # kill camera and launch raw nc over udp
      elif data == "Z":
        self.safe_exit = True # we are done

  def udp_failsafe(self):
    if self.cmd_delay == -1:
      return
    self.last_udp_heartbeat = time.time()
    while not self.safe_exit:
      time.sleep(0.5)
      if time.time() - self.last_udp_heartbeat > self.cmd_delay and self.udp_connected:
        self.trigger_failsafe(source="udp")
    
      
if __name__ == "__main__":
#  def __init__(self,base_ip="10.0.0.2",ping_timeout=8, ping_delay=2, cmd_delay=3,cmd_udp_port=12357,debug=False):

  failsafe = failsafe_and_stuff(ping_timeout = 10, base_ip="10.0.0.2", cmd_delay = 3,debug=True)  


