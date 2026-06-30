#!/usr/bin/env python3
"""
Honda EK OBD2B 9141 Protocol Reader
Premium Dashboard with Custom Gauges - Hondash Style
"""

import socket
import threading
import time
import math
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, Line, Ellipse
from kivy.metrics import dp
from kivy.utils import platform
from kivy.properties import NumericProperty, StringProperty

# ==================== CONFIGURATION ====================
ELM327_IP = "192.168.0.10"
ELM327_PORT = 35000
REFRESH_RATE = 0.2

# Honda 9141 Protocol Commands
HONDA_PIDS = {
    'rpm': '01 0C',
    'coolant': '01 05',
    'speed': '01 0D',
    'throttle': '01 11',
    'intake_temp': '01 0F',
    'engine_load': '01 04',
    'timing': '01 0E',
    'maf': '01 10',
    'fuel_pressure': '01 0A',
    'map': '01 0B'
}

# ==================== FUEL CALCULATOR (km/L) ====================
class FuelCalculator:
    """Calculate fuel consumption in km/L"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.total_fuel = 0.0  # Total fuel used in liters
        self.total_distance = 0.0  # Total distance in km
        self.fuel_efficiency = 0.0  # km/L (average)
        self.last_sample_time = time.time()
        self.samples = []  # Store recent samples for smoothing
    
    def update(self, maf_gps, speed_kmh):
        """Update fuel calculations"""
        current_time = time.time()
        dt = current_time - self.last_sample_time
        
        if dt < 0.1 or speed_kmh < 1:
            return
        
        # Calculate fuel flow from MAF
        # MAF in g/s, AFR for gasoline is 14.7:1
        # Fuel density ~ 750 g/L
        # Fuel flow in L/s = (MAF_gps / 14.7) / 750
        fuel_flow_lps = (maf_gps / 14.7) / 750
        
        # Fuel used in liters
        fuel_used = fuel_flow_lps * dt
        self.total_fuel += fuel_used
        
        # Distance in km
        distance = (speed_kmh / 3600) * dt
        self.total_distance += distance
        
        # Calculate km/L (distance per liter of fuel)
        if self.total_fuel > 0.001 and self.total_distance > 0.1:
            self.fuel_efficiency = self.total_distance / self.total_fuel
        
        # Store sample for smoothing
        if self.fuel_efficiency > 0 and self.fuel_efficiency < 30:
            self.samples.append(self.fuel_efficiency)
            if len(self.samples) > 20:
                self.samples.pop(0)
        
        self.last_sample_time = current_time
    
    def get_average_km_per_liter(self):
        """Get smoothed average fuel efficiency in km/L"""
        if self.samples:
            return sum(self.samples) / len(self.samples)
        return self.fuel_efficiency
    
    def get_total_fuel(self):
        """Get total fuel used in liters"""
        return self.total_fuel
    
    def get_total_distance(self):
        """Get total distance in km"""
        return self.total_distance

# ==================== CUSTOM GAUGE WIDGET ====================
class CircularGauge(Widget):
    """Premium circular gauge with needle and markings"""
    
    value = NumericProperty(0)
    min_value = NumericProperty(0)
    max_value = NumericProperty(100)
    label = StringProperty('')
    unit = StringProperty('')
    warning_threshold = NumericProperty(75)
    danger_threshold = NumericProperty(90)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.needle_angle = -135
        self.target_angle = -135
        self.animation = None
        self.bind(size=self.update_gauge, pos=self.update_gauge)
        self.bind(value=self.update_needle)
        
        self.colors = {
            'background': (0.08, 0.08, 0.12, 1),
            'border': (0.2, 0.4, 0.8, 0.8),
            'text': (1, 1, 1, 1),
            'needle': (1, 0.2, 0.1, 1),
            'center': (0.3, 0.6, 1, 1),
            'tick': (0.6, 0.6, 0.8, 1)
        }
        
        Clock.schedule_once(lambda dt: self.update_gauge(), 0.1)
    
    def update_gauge(self, *args):
        self.canvas.clear()
        with self.canvas:
            size = min(self.width, self.height)
            center_x = self.width / 2
            center_y = self.height / 2
            radius = size * 0.42
            
            # Background
            Color(*self.colors['background'])
            Ellipse(pos=(center_x - radius, center_y - radius), size=(radius*2, radius*2))
            
            # Border
            Color(*self.colors['border'])
            Line(circle=(center_x, center_y, radius), width=3)
            Color(0.3, 0.6, 1, 0.1)
            Line(circle=(center_x, center_y, radius-5), width=20)
            
            # Draw gauge arc
            self.draw_gauge_arc(center_x, center_y, radius)
            
            # Draw tick marks
            self.draw_ticks(center_x, center_y, radius)
            
            # Draw needle
            self.draw_needle(center_x, center_y, radius)
            
            # Draw center cap
            Color(*self.colors['center'])
            Ellipse(pos=(center_x - 12, center_y - 12), size=(24, 24))
            Color(1, 1, 1, 0.3)
            Ellipse(pos=(center_x - 8, center_y - 8), size=(16, 16))
            
            # Draw value text
            Color(*self.colors['text'])
            value_text = f"{int(self.value)}"
            if self.unit:
                value_text += f"\n{self.unit}"
    
    def draw_gauge_arc(self, cx, cy, radius):
        start_angle = -135
        end_angle = 135
        angle_range = end_angle - start_angle
        
        percent = (self.value - self.min_value) / (self.max_value - self.min_value)
        percent = max(0, min(1, percent))
        
        if percent >= self.danger_threshold / 100:
            arc_color = (1, 0, 0, 0.8)
        elif percent >= self.warning_threshold / 100:
            arc_color = (1, 0.8, 0, 0.8)
        else:
            arc_color = (0, 0.8, 0.4, 0.8)
        
        current_angle = start_angle + (angle_range * percent)
        steps = 30
        angle_step = (current_angle - start_angle) / steps
        
        points = []
        for i in range(steps + 1):
            angle = math.radians(start_angle + (i * angle_step))
            r = radius - 15
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            points.extend([x, y])
        
        if len(points) > 4:
            Color(*arc_color)
            Line(points=points, width=8, cap='round', joint='round')
        
        # Background arc
        Color(0.2, 0.2, 0.3, 0.3)
        points_bg = []
        for i in range(steps + 1):
            angle = math.radians(start_angle + (i * angle_range / steps))
            r = radius - 15
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            points_bg.extend([x, y])
        if len(points_bg) > 4:
            Line(points=points_bg, width=4)
    
    def draw_ticks(self, cx, cy, radius):
        start_angle = -135
        end_angle = 135
        angle_range = end_angle - start_angle
        
        num_ticks = 10
        for i in range(num_ticks + 1):
            percent = i / num_ticks
            angle = math.radians(start_angle + (angle_range * percent))
            
            inner_r = radius - 20
            outer_r = radius - 10 if i % 5 == 0 else radius - 15
            
            x1 = cx + inner_r * math.cos(angle)
            y1 = cy + inner_r * math.sin(angle)
            x2 = cx + outer_r * math.cos(angle)
            y2 = cy + outer_r * math.sin(angle)
            
            if i % 5 == 0:
                Color(0.8, 0.8, 1, 0.8)
                width = 2
            else:
                Color(0.4, 0.4, 0.6, 0.5)
                width = 1
            
            Line(points=[x1, y1, x2, y2], width=width)
    
    def draw_needle(self, cx, cy, radius):
        percent = (self.value - self.min_value) / (self.max_value - self.min_value)
        percent = max(0, min(1, percent))
        
        start_angle = -135
        end_angle = 135
        angle_range = end_angle - start_angle
        
        needle_angle = math.radians(start_angle + (angle_range * percent))
        
        needle_length = radius - 25
        x = cx + needle_length * math.cos(needle_angle)
        y = cy + needle_length * math.sin(needle_angle)
        
        # Glow effect
        Color(1, 0.2, 0.1, 0.2)
        Line(points=[cx, cy, x, y], width=12, cap='round')
        
        # Main needle
        Color(1, 0.2, 0.1, 0.9)
        Line(points=[cx, cy, x, y], width=3, cap='round')
        
        # Shadow
        Color(0, 0, 0, 0.3)
        Line(points=[cx+2, cy-2, x+2, y-2], width=3)
    
    def update_needle(self, *args):
        self.update_gauge()

# ==================== CONNECTION POPUP ====================
class ConnectionPopup(Popup):
    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.title = '🔌 Connect to ELM327'
        self.size_hint = (0.85, 0.5)
        self.auto_dismiss = False
        
        layout = BoxLayout(orientation='vertical', spacing=10, padding=15)
        
        layout.add_widget(Label(
            text='Honda EK OBD2B 9141',
            font_size='20sp',
            bold=True,
            color=(0.3, 0.6, 1, 1),
            size_hint_y=0.15
        ))
        
        ip_box = BoxLayout(size_hint_y=0.2)
        ip_box.add_widget(Label(text='IP Address:', size_hint_x=0.3, color=(0.8,0.8,0.8,1)))
        self.ip_input = TextInput(text=ELM327_IP, size_hint_x=0.7, multiline=False)
        ip_box.add_widget(self.ip_input)
        layout.add_widget(ip_box)
        
        port_box = BoxLayout(size_hint_y=0.2)
        port_box.add_widget(Label(text='Port:', size_hint_x=0.3, color=(0.8,0.8,0.8,1)))
        self.port_input = TextInput(text=str(ELM327_PORT), size_hint_x=0.7, multiline=False)
        port_box.add_widget(self.port_input)
        layout.add_widget(port_box)
        
        btn_box = BoxLayout(size_hint_y=0.25, spacing=10)
        connect_btn = Button(text='🚗 CONNECT', background_color=(0, 0.6, 0, 1))
        connect_btn.bind(on_press=self.on_connect)
        cancel_btn = Button(text='✖ CANCEL', background_color=(0.6, 0, 0, 1))
        cancel_btn.bind(on_press=self.dismiss)
        btn_box.add_widget(connect_btn)
        btn_box.add_widget(cancel_btn)
        layout.add_widget(btn_box)
        
        self.status = Label(text='Ready to connect', size_hint_y=0.2, color=(0.8,0.8,0.8,1))
        layout.add_widget(self.status)
        
        self.add_widget(layout)
    
    def on_connect(self, instance):
        ip = self.ip_input.text.strip()
        try:
            port = int(self.port_input.text.strip())
            self.status.text = f'Connecting to {ip}:{port}...'
            self.status.color = (1,1,0,1)
            
            def test():
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    sock.connect((ip, port))
                    sock.close()
                    Clock.schedule_once(lambda dt: self.success(ip, port), 0)
                except Exception as e:
                    Clock.schedule_once(lambda dt: self.fail(str(e)), 0)
            
            threading.Thread(target=test, daemon=True).start()
        except:
            self.status.text = '❌ Invalid port number'
            self.status.color = (1,0,0,1)
    
    def success(self, ip, port):
        self.dismiss()
        if self.callback:
            self.callback(ip, port)
    
    def fail(self, error):
        self.status.text = f'❌ Failed: {error[:30]}'
        self.status.color = (1,0,0,1)

# ==================== MAIN DASHBOARD ====================
class HondaDash(BoxLayout):
    """Premium dashboard with custom circular gauges"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = [5, 5]
        self.spacing = 5
        
        with self.canvas.before:
            Color(0.02, 0.02, 0.05, 1)
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)
        
        self.ecu_data = {
            'rpm': 0, 'coolant': 0, 'speed': 0,
            'throttle': 0, 'intake_temp': 0, 'engine_load': 0,
            'timing': 0, 'maf': 0, 'fuel_pressure': 0,
            'map': 0, 'fuel_avg': 0
        }
        self.sock = None
        self.connected = False
        self.running = False
        self.fuel_calc = FuelCalculator()
        
        self.build_ui()
        Clock.schedule_once(lambda dt: self.show_connection(), 0.5)
    
    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
    
    def build_ui(self):
        self.clear_widgets()
        
        # HEADER
        header = BoxLayout(size_hint_y=0.07, spacing=10, padding=[10,5])
        with header.canvas.before:
            Color(0.05, 0.05, 0.1, 1)
            self.header_rect = Rectangle(size=header.size, pos=header.pos)
        header.bind(size=self._update_header_rect, pos=self._update_header_rect)
        
        title = Label(
            text='🏎️ HONDA EK OBD2B',
            font_size='18sp',
            bold=True,
            color=(0.3, 0.6, 1, 1),
            halign='left',
            size_hint_x=0.5
        )
        header.add_widget(title)
        
        self.status_label = Label(
            text='🔴 DISCONNECTED',
            font_size='13sp',
            color=(0.8,0.8,0.8,1),
            size_hint_x=0.3
        )
        header.add_widget(self.status_label)
        
        self.connect_btn = Button(
            text='⚡ CONNECT',
            size_hint_x=0.2,
            background_color=(0.2, 0.6, 1, 1),
            font_size='12sp',
            bold=True
        )
        self.connect_btn.bind(on_press=self.toggle_connection)
        header.add_widget(self.connect_btn)
        self.add_widget(header)
        
        # GAUGES
        scroll = ScrollView(do_scroll_x=False)
        scroll.bar_width = 2
        
        is_portrait = Window.width < Window.height
        cols = 2 if is_portrait else 3
        
        grid = GridLayout(
            cols=cols,
            spacing=10,
            padding=10,
            size_hint_y=None,
            row_force_default=True,
            row_default_height=dp(250)
        )
        grid.bind(minimum_height=grid.setter('height'))
        
        # Define gauges - Fuel Avg in km/L (0-30 range)
        gauge_configs = [
            ('RPM', 'rpm', 0, 8000, 'RPM', 6000, 7000),
            ('Speed', 'speed', 0, 200, 'km/h', 120, 160),
            ('Coolant', 'coolant', 0, 120, '°C', 90, 100),
            ('Throttle', 'throttle', 0, 100, '%', 75, 90),
            ('Fuel Avg', 'fuel_avg', 0, 30, 'km/L', 20, 25),  # km/L!
            ('Engine Load', 'engine_load', 0, 100, '%', 75, 90),
            ('Intake Temp', 'intake_temp', 0, 80, '°C', 60, 70),
            ('Timing', 'timing', -20, 40, '°', 30, 35),
            ('MAF', 'maf', 0, 100, 'g/s', 70, 85),
        ]
        
        self.gauges = {}
        for label, key, min_v, max_v, unit, warn, danger in gauge_configs:
            gauge = CircularGauge(
                min_value=min_v,
                max_value=max_v,
                label=label,
                unit=unit,
                warning_threshold=warn,
                danger_threshold=danger
            )
            gauge.size_hint = (1, 1)
            self.gauges[key] = gauge
            grid.add_widget(gauge)
        
        scroll.add_widget(grid)
        self.add_widget(scroll)
        
        # FOOTER - Trip Info
        footer = BoxLayout(size_hint_y=0.06, padding=[10,2], spacing=10)
        with footer.canvas.before:
            Color(0.05, 0.05, 0.1, 1)
            self.footer_rect = Rectangle(size=footer.size, pos=footer.pos)
        footer.bind(size=self._update_footer_rect, pos=self._update_footer_rect)
        
        self.trip_label = Label(
            text='⛽ 0.0L  •  📍 0.0km  •  📊 0.0 km/L',
            font_size='12sp',
            color=(0.4,0.4,0.6,1),
            halign='center'
        )
        footer.add_widget(self.trip_label)
        self.add_widget(footer)
        
        Window.bind(on_resize=self.on_resize)
    
    def _update_header_rect(self, *args):
        self.header_rect.pos = args[0].pos
        self.header_rect.size = args[0].size
    
    def _update_footer_rect(self, *args):
        self.footer_rect.pos = args[0].pos
        self.footer_rect.size = args[0].size
    
    def on_resize(self, *args):
        Clock.schedule_once(lambda dt: self.rebuild_ui(), 0.1)
    
    def rebuild_ui(self):
        if self.connected:
            self.build_ui()
            self.update_gauges()
        else:
            self.build_ui()
    
    def toggle_connection(self, instance):
        if self.connected:
            self.disconnect()
        else:
            self.show_connection()
    
    def show_connection(self, instance=None):
        popup = ConnectionPopup(self.connect)
        popup.open()
    
    def connect(self, ip, port):
        def connect_thread():
            try:
                self.update_status('CONNECTING...', (1,1,0,1))
                
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(5.0)
                self.sock.connect((ip, port))
                
                init_cmds = [
                    "AT Z", "AT E0", "AT L0", "AT SP 3",
                    "AT IB 96", "AT ST 96", "AT SH 81 11 F1",
                    "AT FI", "AT H0", "AT S0"
                ]
                
                for cmd in init_cmds:
                    self.sock.sendall(f"{cmd}\r".encode('utf-8'))
                    time.sleep(0.1)
                    self.sock.recv(1024)
                
                self.connected = True
                self.running = True
                self.update_status('CONNECTED ✅', (0,1,0,1))
                self.fuel_calc.reset()
                
                Clock.schedule_interval(self.read_data, REFRESH_RATE)
                
            except Exception as e:
                self.update_status(f'FAILED', (1,0,0,1))
                self.connected = False
                self.sock = None
        
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def disconnect(self):
        self.running = False
        self.connected = False
        Clock.unschedule(self.read_data)
        
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
        
        self.update_status('DISCONNECTED', (0.8,0.8,0.8,1))
    
    def read_data(self, dt):
        if not self.running or not self.sock:
            return False
        
        try:
            # Read RPM
            self.sock.sendall(b"01 0C\r")
            response = self.read_response()
            self.parse_value(response, '410C', 'rpm', lambda x: int(((x[0]*256)+x[1])/4))
            
            # Read Speed
            self.sock.sendall(b"01 0D\r")
            response = self.read_response()
            self.parse_value(response, '410D', 'speed', lambda x: x[0])
            
            # Read Coolant Temp
            self.sock.sendall(b"01 05\r")
            response = self.read_response()
            self.parse_value(response, '4105', 'coolant', lambda x: x[0] - 40)
            
            # Read Throttle
            self.sock.sendall(b"01 11\r")
            response = self.read_response()
            self.parse_value(response, '4111', 'throttle', lambda x: int(x[0] / 2.55))
            
            # Read Engine Load
            self.sock.sendall(b"01 04\r")
            response = self.read_response()
            self.parse_value(response, '4104', 'engine_load', lambda x: int(x[0] * 100 / 255))
            
            # Read Intake Temp
            self.sock.sendall(b"01 0F\r")
            response = self.read_response()
            self.parse_value(response, '410F', 'intake_temp', lambda x: x[0] - 40)
            
            # Read Timing
            self.sock.sendall(b"01 0E\r")
            response = self.read_response()
            self.parse_value(response, '410E', 'timing', lambda x: x[0] / 2 - 64)
            
            # Read MAF
            self.sock.sendall(b"01 10\r")
            response = self.read_response()
            self.parse_value(response, '4110', 'maf', lambda x: ((x[0]*256)+x[1]) / 100)
            
            # Calculate Fuel Average in km/L
            speed = self.ecu_data.get('speed', 0)
            maf = self.ecu_data.get('maf', 0)
            if speed > 0 and maf > 0:
                self.fuel_calc.update(maf, speed)
                self.ecu_data['fuel_avg'] = self.fuel_calc.get_average_km_per_liter()
            
            # Update trip info - showing km/L
            total_fuel = self.fuel_calc.get_total_fuel()
            total_dist = self.fuel_calc.get_total_distance()
            avg_kmpl = self.fuel_calc.get_average_km_per_liter()
            
            trip_text = f'⛽ {total_fuel:.1f}L  •  📍 {total_dist:.1f}km'
            if total_dist > 0:
                trip_text += f'  •  📊 {avg_kmpl:.1f} km/L'
            Clock.schedule_once(lambda dt, t=trip_text: setattr(self.trip_label, 'text', t), 0)
            
            # Update gauges
            Clock.schedule_once(lambda dt: self.update_gauges(), 0)
            
            return True
            
        except Exception as e:
            self.handle_error()
            return False
    
    def read_response(self):
        buffer = ""
        try:
            while ">" not in buffer:
                chunk = self.sock.recv(1024).decode('utf-8', errors='ignore')
                if not chunk:
                    break
                buffer += chunk
                if len(buffer) > 1024:
                    break
            return buffer.replace(" ", "").strip()
        except:
            return ""
    
    def parse_value(self, response, key, data_key, converter):
        try:
            if key in response:
                idx = response.find(key) + len(key)
                hex_data = response[idx:idx+4]
                if len(hex_data) >= 4:
                    bytes_data = [int(hex_data[i:i+2], 16) for i in range(0, 4, 2)]
                    value = converter(bytes_data)
                    if -100 < value < 10000:
                        self.ecu_data[data_key] = value
        except:
            pass
    
    def update_gauges(self):
        for key, gauge in self.gauges.items():
            if key in self.ecu_data:
                gauge.value = self.ecu_data[key]
    
    def update_status(self, text, color):
        def update():
            self.status_label.text = text
            self.status_label.color = color
            if 'CONNECTED' in text:
                self.connect_btn.text = '🔌 DISCONNECT'
                self.connect_btn.background_color = (0.8, 0.2, 0.2, 1)
            else:
                self.connect_btn.text = '⚡ CONNECT'
                self.connect_btn.background_color = (0.2, 0.6, 1, 1)
        
        Clock.schedule_once(lambda dt: update(), 0)
    
    def handle_error(self):
        self.running = False
        self.update_status('CONNECTION LOST', (1,0.5,0,1))
        Clock.unschedule(self.read_data)
        
        def reconnect():
            time.sleep(3)
            if not self.running and self.connected:
                self.update_status('RECONNECTING...', (1,1,0,1))
                self.connect(ELM327_IP, ELM327_PORT)
        
        threading.Thread(target=reconnect, daemon=True).start()

# ==================== APPLICATION ====================
class HondaDashApp(App):
    def build(self):
        if platform not in ('android', 'ios'):
            Window.size = (1024, 600)
        return HondaDash()
    
    def on_stop(self):
        if hasattr(self, 'root'):
            self.root.disconnect()

if __name__ == '__main__':
    HondaDashApp().run()