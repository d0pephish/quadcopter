#!/usr/bin/python2.7

import ping, os, time, socket, threading

class failsafe_and_stuff:

  def __init__(self,base_ip="10.0.0.2",ping_timeout=8, ping_delay=2, cmd_delay=3,cmd_udp_port=12357,debug=False):
    self.base_ip = base_ip
    self.connected = False
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
          self.trigger_failsafe()

  def trigger_failsafe(self):
    self.debug("failsafe activated")
    #os.system("reboot")
    
  def trigger_deauth(self):
    self.debug("deauth activated")
    pass

  def udp_listener(self):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0",self.cmd_udp_port))
    while not self.safe_exit:
      data, addr = sock.recvfrom(1)
      print "received message:", data
      if addr[0] == self.base_ip:
        self.last_udp_heartbeat = time.time()
      if data == "A":
        self.connnected = True
        pass #alive
      elif data == "K":
        self.add_thread_and_start(threading.Thread(target=self.trigger_failsafe)) # kill
      elif data == "D":
        self.add_thread_and_start(threading.Thread(target=self.trigger_deauth)) # deauth
      elif data == "Z":
        self.safe_exit = True # we are done

  def udp_failsafe(self):
    if self.cmd_delay == -1:
      return
    self.last_udp_heartbeat = time.time()
    while not self.safe_exit:
      time.sleep(0.5)
      if time.time() - self.last_udp_heartbeat > self.cmd_delay:
        self.trigger_failsafe()
    
      
if __name__ == "__main__":
#  def __init__(self,base_ip="10.0.0.2",ping_timeout=8, ping_delay=2, cmd_delay=3,cmd_udp_port=12357,debug=False):

  failsafe = failsafe_and_stuff(ping_timeout = -1, base_ip="127.0.0.1", cmd_delay = -1,debug=True)  


"""
#!/bin/bash

#don't activate until comms are established
while true; do
  ping 10.0.0.2 -W1 -c 1 2>/dev/null 1>/dev/null && break
done

echo "Connection with client established. Failsafe activated."

while true; do
  test -e /tmp/disable_failsafe && break
  ping 10.0.0.2 -c 1 -W5 2>/dev/null 1>/dev/null && ( echo good heartbeat at $(date) ) || ( reboot -f || init 0 )
  sleep 2
done
"""
