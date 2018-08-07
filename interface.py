import curses, time, sys, socket, threading

from dronekit import *


# Set up velocity mappings
# velocity_x > 0 => fly North
# velocity_x < 0 => fly South
# velocity_y > 0 => fly East
# velocity_y < 0 => fly West
# velocity_z < 0 => ascend
# velocity_z > 0 => descend
SOUTH = (-1,0,0,2)
NORTH = (1,0,0,2)
EAST = (0,1,0,2)
WEST = (0,-1,0,2)
UP = (0,0,-1,2)
DOWN = (0,0,1,2)


class quad_controller:

  def get_location_metres(self,original_location, dNorth, dEast):
      """
      Returns a LocationGlobal object containing the latitude/longitude `dNorth` and `dEast` metres from the 
      specified `original_location`. The returned LocationGlobal has the same `alt` value
      as `original_location`.

      The function is useful when you want to move the vehicle around specifying locations relative to 
      the current vehicle position.

      The algorithm is relatively accurate over small distances (10m within 1km) except close to the poles.

      For more information see:
      http://gis.stackexchange.com/questions/2951/algorithm-for-offsetting-a-latitude-longitude-by-some-amount-of-meters
      """
      earth_radius = 6378137.0 #Radius of "spherical" earth
      #Coordinate offsets in radians
      dLat = dNorth/earth_radius
      dLon = dEast/(earth_radius*math.cos(math.pi*original_location.lat/180))

      #New position in decimal degrees
      newlat = original_location.lat + (dLat * 180/math.pi)
      newlon = original_location.lon + (dLon * 180/math.pi)
      if type(original_location) is LocationGlobal:
          targetlocation=LocationGlobal(newlat, newlon,original_location.alt)
      elif type(original_location) is LocationGlobalRelative:
          targetlocation=LocationGlobalRelative(newlat, newlon,original_location.alt)
      else:
          raise Exception("Invalid Location object passed")
          
      return targetlocation;


  def get_distance_metres(self, aLocation1, aLocation2):
      """
      Returns the ground distance in metres between two LocationGlobal objects.

      This method is an approximation, and will not be accurate over large distances and close to the 
      earth's poles. It comes from the ArduPilot test code: 
      https://github.com/diydrones/ardupilot/blob/master/Tools/autotest/common.py
      """
      dlat = aLocation2.lat - aLocation1.lat
      dlong = aLocation2.lon - aLocation1.lon
      return math.sqrt((dlat*dlat) + (dlong*dlong)) * 1.113195e5


  def get_bearing(self, aLocation1, aLocation2):
      """
      Returns the bearing between the two LocationGlobal objects passed as parameters.

      This method is an approximation, and may not be accurate over large distances and close to the 
      earth's poles. It comes from the ArduPilot test code: 
      https://github.com/diydrones/ardupilot/blob/master/Tools/autotest/common.py
      """	
      off_x = aLocation2.lon - aLocation1.lon
      off_y = aLocation2.lat - aLocation1.lat
      bearing = 90.00 + math.atan2(-off_y, off_x) * 57.2957795
      if bearing < 0:
          bearing += 360.00
      return bearing;


  def goto(self,dNorth=-1, dEast=-1, gotoFunction=False):
      if gotoFunction == False:
        gotoFunction = self.vehicle.simple_goto
      if dNorth == -1:
        dNorth = self.coords_goto[0]
      if dEast == -1:
        dEast = self.coords_goto[1]
      self.put("goto started, dNorth:%f, dEast:%f" %(dNorth,dEast))
      currentLocation=self.vehicle.location.global_relative_frame
      targetLocation=self.get_location_metres(currentLocation, dNorth, dEast)
      targetDistance=self.get_distance_metres(currentLocation, targetLocation)
      gotoFunction(targetLocation)

      while self.vehicle.mode.name=="GUIDED" and self.started: #Stop action if we are no longer in guided mode.
          remainingDistance=self.get_distance_metres(self.vehicle.location.global_frame, targetLocation)
          self.put("Distance to target: %s" % (remainingDistance))
          if remainingDistance<=targetDistance*0.01: #Just below target, in case of undershoot.
              self.put("Reached target")
              break;
          time.sleep(1)



  def send_ned_velocity(self,velocity_x, velocity_y, velocity_z, duration):
      """
      Move vehicle in direction based on specified velocity vectors.
      """
      msg = self.vehicle.message_factory.set_position_target_local_ned_encode(
          0,       # time_boot_ms (not used)
          0, 0,    # target system, target component
          mavutil.mavlink.MAV_FRAME_LOCAL_NED, # frame
          0b0000111111000111, # type_mask (only speeds enabled)
          0, 0, 0, # x, y, z positions (not used)
          velocity_x, velocity_y, velocity_z, # x, y, z velocity in m/s
          0, 0, 0, # x, y, z acceleration (not supported yet, ignored in GCS_Mavlink)
          0, 0)    # yaw, yaw_rate (not supported yet, ignored in GCS_Mavlink)


      # send command to vehicle on 1 Hz cycle
      for x in range(0,duration):
          self.vehicle.send_mavlink(msg)
          time.sleep(0.1)

  def arm_and_takeoff(self,aTargetAltitude="-1"):
      if aTargetAltitude == "-1":
        aTargetAltitude = self.starting_height
      """
      Arms vehicle and fly to aTargetAltitude.
      """

      self.put("Basic pre-arm checks")
      # Don't try to arm until autopilot is ready
      while not self.vehicle.is_armable:
          self.put(" Waiting for vehicle to initialise...")
          time.sleep(1)

      self.put("Arming motors")
      # Copter should arm in GUIDED mode
      self.vehicle.mode    = VehicleMode("GUIDED")
      self.vehicle.armed   = True

      # Confirm vehicle armed before attempting to take off
      while not self.vehicle.armed:
          self.put(" Waiting for arming...")
          time.sleep(1)

      self.put("Taking off!")
      self.vehicle.simple_takeoff(aTargetAltitude) # Take off to target altitude

      # Wait until the vehicle reaches a safe height before processing the goto (otherwise the command
      #  after Vehicle.simple_takeoff will execute immediately).
      timeout = 4
      while timeout>0:
          timeout = timeout - 1
          self.put(" Altitude: %s" % self.vehicle.location.global_relative_frame.alt)
          #Break and return from function just below target altitude.
          if self.vehicle.location.global_relative_frame.alt>=aTargetAltitude*0.95:
              self.put("Reached target altitude")
              break
          time.sleep(1)

  def condition_yaw(self,heading, relative=False):
      if relative:
          is_relative=1 #yaw relative to direction of travel
      else:
          is_relative=0 #yaw is an absolute angle
      # create the CONDITION_YAW command using command_long_encode()
      msg = self.vehicle.message_factory.command_long_encode(
          0, 0,    # target system, target component
          mavutil.mavlink.MAV_CMD_CONDITION_YAW, #command
          0, #confirmation
          heading,    # param 1, yaw in degrees
          0,          # param 2, yaw speed deg/s
          1,          # param 3, direction -1 ccw, 1 cw
          is_relative, # param 4, relative offset 1, absolute angle 0
          0, 0, 0)    # param 5 ~ 7 not used
      # send command to vehicle
      self.vehicle.send_mavlink(msg)




  class stdout_wrapper:
    ##doesn't work...curses overrides 
    def __init__(self,parent):
      self.parent = parent

    def write(self,txt):
      self.parent.put(self,txt)


  def build_real_connect(self):
    self.connection_string = "%s:%d" % ( self.mavlink_ip, self.mavlink_port)

  def build_simulated_connect(self):
    import dronekit_sitl
    sitl = dronekit_sitl.start_default()
    self.connection_string = sitl.connection_string()

  def __init__(self,mode="sim", ip="10.0.0.1", mavlink_ip= "10.0.0.2", starting_height = 1, mavlink_port=6000, command_port=12357):
    self.line = 0
    self.mavlink_ip = mavlink_ip
    self.orig_stdout = sys.stdout
    self.orig_stderr = sys.stderr
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.mavlink_port = mavlink_port
    self.command_port = command_port
    self.coors_goto = False
    self.ip = ip
    self.started = True
    self.threads = []
    self.coords = {} #TODO: update this, implement manual entry
    self.starting_height = starting_height

    if mode == "sim":
      self.build_simulated_connect()
    else:
      self.build_real_connect()

    #output = self.stdout_wrapper(self)
    #self.stdout = output
    #self.stderr = output
    

  def build_curses(self):
    self.stdscr = curses.initscr()

    curses.noecho()
    curses.cbreak()

    self.stdscr.keypad(1)

  def teardown(self):
    curses.nocbreak()
    self.stdscr.keypad(0);
    curses.echo()
    curses.endwin()
    sys.stdout = self.orig_stdout
    sys.stderr = self.orig_stderr
    self.vehicle.close()
    for t in self.threads:
      t.join()



  def put(self,s):
    line = self.line
    self.line += 1
    self.stdscr.addstr(line,0,str(s))
    self.stdscr.refresh()

  def clear(self):
    self.line = 0;
    self.stdscr.clear()

  def quad_connect(self):
    self.vehicle = connect(self.connection_string, wait_ready=True,status_printer = self.put)
    self.put("Connecting to vehicle on: %s" % self.connection_string)
    self.vehicle.parameters['RTL_ALT'] = 0

  def send_command(self,c):
    self.sock.sendto(c, (self.ip, self.command_port))
  
  def keep_alive(self):
    while self.started:
      self.send_command("A")
      time.sleep(0.5) 
  
  def get_char(self):
    c = self.stdscr.getch()
    if c < 127:
      char = str(chr(c)).lower()
      return char
    else:
      return False

  def start_thread_and_append(self, method):
    t = threading.Thread(target=method)
    t.start()
    self.threads.append(t)
  
  def read_coords(self, index):
    try:
      self.put("coordinates at index %s is: lat:%f,lon:%f" % (index, self.coords[index][0], self.coords[index][1]))
    except:
      self.put("error reading from coords at index:%s" % (index))

  def start(self):
    self.start_thread_and_append(self.keep_alive)
    self.build_curses()
    self.quad_connect()
    time.sleep(0.5)
    while self.started:
      self.clear()
      self.put(self.vehicle.gps_0)
      self.put(self.vehicle.battery)
      self.put("Last Hearbeat: %s" % self.vehicle.last_heartbeat)
      self.put("Start Alt:%d (m)" % (self.starting_height))
      self.put("Cur Alt:%s (m)" % (self.vehicle.location.global_relative_frame.alt))
      self.put("Cur Lat:%s (m)" % (self.vehicle.location.global_relative_frame.lat))
      self.put("Cur Lon:%s (m)" % (self.vehicle.location.global_relative_frame.lon))
      self.put("Armable: %s" % self.vehicle.is_armable)
      self.put("System Status: %s" % self.vehicle.system_status.state)
      self.put("Mode: %s" % self.vehicle.mode.name)
      self.put("WASD=>NSEW move. EQ=>CW/CCW yaw.")
      self.put("R:RTL T:take-off L:land I:view coords")
      self.put("H:change start height P:deauth")
      self.put("C:QGC camera N:raw stream")
      self.put("M:N+save to disk. B:no cam")
      self.put("K:kill ]:failsafe \\:no failsafe")
      self.put("H:higher J:lower Y:coord G:goto")
      self.put("X:exit on remote end Z:quit local")
      c = self.stdscr.getch()
      if c < 127:
        char = str(chr(c)).lower()
      else:
        pass
      if char == "z":
        self.started = False
      elif char == " ":
        pass
      elif char == "w":
        self.put("Going north for 0.2 seconds.")
        self.send_ned_velocity(*NORTH)
      elif char == "a":
        self.put("Going west for 0.2 seconds.")
        self.send_ned_velocity(*WEST)
      elif char == "s":
        self.put("Going south for 0.2 seconds.")
        self.send_ned_velocity(*SOUTH)
      elif char == "d":
        self.put("Going east for 0.2 seconds.")
        self.send_ned_velocity(*EAST)
      elif char == "h":
        self.put("Going higher for 0.2 seconds.")
        self.send_ned_velocity(*UP)
      elif char == "j":
        self.put("Going lower for 0.2 seconds.")
        self.send_ned_velocity(*DOWN)
      elif char == "e":
        self.put("Adjusting yaw CW for 10 degrees.")
        self.condition_yaw(10,relative=True)
      elif char == "q":
        self.put("Adjusting yaw CCW for 10 degrees.")
        self.condition_yaw(-10,relative=True)
      elif char == "l":
        self.put("Going to land.")
        self.vehicle.mode = VehicleMode("LAND")
      elif char == "t":
        self.put("Taking off to %d meter." % self.starting_height)
        self.start_thread_and_append(self.arm_and_takeoff)
      elif char == "g":
        self.put("Which coord index do you want to go to (0-9)")
        char = self.get_char()
        try:
          if int(char)>=0 and int(char) < 9:
            if self.coords[char]:
              self.read_coords(char)
              self.coords_goto = self.coords[char] 
        except:
          continue
        self.put("press y to confirm")
        char = self.get_char()
        if char == "y" :
          self.start_thread_and_append(self.goto)
 
      elif char == "r":
        self.put("Returning to Launch.")
        self.vehicle.parameters['RTL_ALT'] = 0
        self.vehicle.parameters['RTL_ALT_FINAL'] = 0
        self.vehicle.parameters['RTL_CLIMB_MIN'] = 0
        self.vehicle.mode = VehicleMode("RTL")
      elif char == "k":
        self.send_command("K")
        self.put("activating killswitch")
      elif char == "c":
        self.send_command("C")
        self.put("turning on QGC camera")
      elif char == "m":
        self.send_command("M")
        self.put("saving to disk, then turning on nc camera")
      elif char == "b":
        self.send_command("B")
        self.put("turning off camera")
      elif char == "n":
        self.send_command("N")
        self.put("turning on nc camera")
      elif char == "]":
        self.send_command("F")
        self.put("failsafe enabled")
      elif char == "x":
        self.send_command("X")
        self.put("remote exit")
      elif char == "p":
        self.send_command("D")
        self.put("activating deauth")
      elif char == "\\":
        self.send_command("Z")
        self.put("disabling failsafe")
      elif char == "y":
        self.put("Which coord index do you want to update (0-9)")
        char = self.get_char()
        try:
          if int(char)>=0 and int(char) < 9:
            self.put("lat:")
            curses.nocbreak()
            curses.echo()
            lat = self.stdscr.getstr()
            self.put("lon:")
            lon = self.stdscr.getstr()
            self.put("got lat:%s, long:%s" % (lat,lon))
            curses.cbreak()
            curses.noecho()
            self.coords[char] = (float(lat),float(lon))
            self.put("updated...")
        except:
          pass
        self.read_coords(char)
        self.put("press enter to continue")
        self.get_char()
      elif char == "h":
        self.put("What new default height would you like to use?")
        char = self.get_char()
        try:
          if int(char)>0 and int(char) < 50:
            self.starting_height = int(char)
        except:
          pass
    self.teardown()


if __name__ == "__main__":
  controller = quad_controller(ip="127.0.0.1",mode="sim")
  controller.start()

