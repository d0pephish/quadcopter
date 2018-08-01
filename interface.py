import curses, time, sys, socket, threading

from dronekit import connect, VehicleMode, mavutil


# Set up velocity mappings
# velocity_x > 0 => fly North
# velocity_x < 0 => fly South
# velocity_y > 0 => fly East
# velocity_y < 0 => fly West
# velocity_z < 0 => ascend
# velocity_z > 0 => descend
SOUTH = (-1,0,0,5)
NORTH = (1,0,0,5)
EAST = (0,1,0,5)
WEST = (0,-1,0,5)


class quad_controller:

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

  def arm_and_takeoff(self,aTargetAltitude):
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
    self.connect_string = "%s:%d" % ( self.ip, self.mavlink_port)

  def build_simulated_connect(self):
    import dronekit_sitl
    sitl = dronekit_sitl.start_default()
    self.connection_string = sitl.connection_string()

  def __init__(self,mode="sim", ip="10.0.0.1", starting_height = 1, mavlink_port=5600, command_port=12357):
    self.line = 0
    self.orig_stdout = sys.stdout
    self.orig_stderr = sys.stderr
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.mavlink_port = mavlink_port
    self.command_port = command_port
    self.ip = ip
    self.started = True
    self.threads = []
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
    self.threads.append[t]

  def start(self):
    self.start_thread_and_append(self.keep_alive)
    self.build_curses()
    self.quad_connect()
    while self.started:
      self.clear()
      self.put(self.vehicle.gps_0)
      self.put(self.vehicle.battery)
      self.put("Last Hearbeat: %s" % self.vehicle.last_heartbeat)
      self.put("Start Alt:%d (m) Cur Alt: %s" % (self.starting_height, self.vehicle.location.global_relative_frame.alt))
      self.put("Armable: %s" % self.vehicle.is_armable)
      self.put("System Status: %s" % self.vehicle.system_status.state)
      self.put("Mode: %s" % self.vehicle.mode.name)
      self.put("WASD for NSEW movement. EQ for CW/CCW yaw.")
      self.put("R to RTL, F to take-off, L to land. U to update.")
      self.put("H to change starting height. P for deauth packet broadcast.")
      self.put("K to activate killswitch. \\ to deactivate killswitch")
      c = self.stdscr.getch()
      if c < 127:
        char = str(chr(c)).lower()
      else:
        pass
      if char == "z":
        self.started = False
      elif char == "u":
        pass
      elif char == "w":
        self.put("Going north for 0.5 seconds.")
        self.send_ned_velocity(*NORTH)
      elif char == "a":
        self.put("Going west for 0.5 seconds.")
        self.send_ned_velocity(*WEST)
      elif char == "s":
        self.put("Going south for 0.5 seconds.")
        self.send_ned_velocity(*SOUTH)
      elif char == "d":
        self.put("Going east for 0.5 seconds.")
        self.send_ned_velocity(*EAST)
      elif char == "e":
        self.put("Adjusting yaw CW for 10 degrees.")
        self.condition_yaw(10,relative=True)
      elif char == "q":
        self.put("Adjusting yaw CCW for 10 degrees.")
        self.condition_yaw(-10,relative=False)
      elif char == "l":
        self.put("Going to land.")
        self.vehicle.mode = VehicleMode("LAND")
      elif char == "f":
        self.put("Taking off to %d meter." % 1)
        self.arm_and_takeoff(1)
        #self.vehicle.mode = VehicleMode("LOITER")
      elif char == "r":
        self.put("Returning to Launch.")
        self.vehicle.parameters['RTL_ALT'] = 0
        self.vehicle.parameters['RTL_ALT_FINAL'] = 0
        self.vehicle.parameters['RTL_CLIMB_MIN'] = 0
        self.vehicle.mode = VehicleMode("RTL")
      elif char == "k":
        self.send_command("K")
        self.put("activating killswitch")
      elif char == "p":
        self.send_command("D")
        self.put("activating deauth")
      elif char == "\\":
        self.send_command("Z")
        self.put("disarming failsafe")

      elif char == "h":
        self.put("What new default height would you like to use?")
        char = self.get_char()
        try:
          if int(char)>0 and int(char) < 50:
            self.starting_height = int(chr)
        except:
          pass
    self.teardown()


if __name__ == "__main__":
  controller = quad_controller(ip="127.0.0.1")
  controller.start()

