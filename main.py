import MetaTrader5 as mt5
from datetime import datetime
import logging
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.textfield import MDTextField
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.resources import resource_add_path
from kivy.uix.scrollview import ScrollView
from kivymd.icon_definitions import md_icons

resource_add_path(r'C:\Users\kkayg\AppData\Roaming\Python\Python312\site-packages\kivymd')

# Set up logging
logging.basicConfig(level=logging.INFO)

# Updated KV design
kv = '''
ScreenManager:
    LoginScreen:
    TradingScreen:

<LoginScreen>:
    name: 'SFX Login'
    MDBoxLayout:
        orientation: 'vertical'
        padding: dp(20)
        spacing: dp(20)
        MDLabel:
            text: "SlingShotFX(Phiri)"
            halign: "center"
        MDIcon:
            icon: "account"
            halign: "center"
        MDTextField:
            id: server_input
            hint_text: "Server"
            text: ''
        MDIcon:
            icon: "key"
            halign: "center"
        MDTextField:
            id: password_input
            hint_text: "Password"
            password: True
            password_mask: '*'
        MDRaisedButton:
            text: "Login"
            pos_hint: {"center_x": 0.5}
            on_press: app.mt5_login(server_input.text, '154948014', password_input.text)

<TradingScreen>:
    name: 'trading'
    MDBoxLayout:
        orientation: 'vertical'
        padding: dp(20)
        spacing: dp(20)
        MDTextField:
            id: symbol_input
            hint_text: "Currency Symbol"
            text: ""
        MDTextField:
            id: volume_input
            hint_text: "Volume"
            text: ""
        MDTextField:
            id: trades_input
            hint_text: "Max Trades"
            text: ""
        MDRaisedButton:
            text: "Start Trading"
            id: start_button
            pos_hint: {"center_x": 0.5}
            on_press: app.start_trading(symbol_input.text, volume_input.text, trades_input.text)
        MDRaisedButton:
            text: "Stop Trading"
            id: stop_button
            pos_hint: {"center_x": 0.5}
            disabled: True
            on_press: app.stop_trading()
        MDRaisedButton:
            text: "Clear Log"
            pos_hint: {"center_x": 0.5}
            on_press: app.clear_log()
        ScrollView:
            MDBoxLayout:
                id: log_box
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(10)
        MDLabel:
            text: ""
            id: trade_status_label
            halign: "center"
        MDLabel:
            text: "MetaTrader5"
            id: countdown_label
            halign: "center"
'''

class LoginScreen(MDScreen):
    pass

class TradingScreen(MDScreen):
    pass

class SlingShotFX(MDApp):
    trades_executed = 0
    next_trade_time = None
    trading_event = None
    ellipsis_text = "Executing"
    ellipsis_cycle_event = None

    def build(self):
        self.icon = r'C:\Users\kkayg\Desktop\roboto\sfx.png'
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"
        return Builder.load_string(kv)

    def mt5_login(self, server, login_id, password):
        if not mt5.initialize(login=int(login_id), password=password, server=server):
            logging.error("initialize() failed, error code = %s", mt5.last_error())
            self.update_log(f"Login failed: {mt5.last_error()}")
            return False
        logging.info("Connected to %s", server)
        self.update_log(f"Connected to {server}")
        self.root.current = 'trading'
        return True

    def start_ellipsis_animation(self):
        self.ellipsis_cycle_event = Clock.schedule_interval(lambda dt: self.cycle_ellipsis(), 0.5)

    def stop_ellipsis_animation(self):
        if self.ellipsis_cycle_event:
            self.ellipsis_cycle_event.cancel()

    def cycle_ellipsis(self):
        if len(self.ellipsis_text) >= 12:  # Maximum length reached, reset
            self.ellipsis_text = "Executing"
        else:
            self.ellipsis_text += "."
        self.update_trade_status(self.ellipsis_text)

    def start_trading(self, symbol, volume, max_trades):
        self.trades_executed = 0
        self.max_trades = int(max_trades)
        self.volume = float(volume)
        self.trading_event = Clock.schedule_interval(lambda dt: self.trade(symbol), 5)
        self.root.get_screen('trading').ids.start_button.disabled = True
        self.root.get_screen('trading').ids.stop_button.disabled = False
        logging.info("Trading started.")
        self.update_log("Trading started.")
        self.update_trade_status("Executing")
        self.start_ellipsis_animation()

    def stop_trading(self):
        if self.trading_event:
            self.trading_event.cancel()
            self.trading_event = None
            mt5.shutdown()
            self.root.get_screen('trading').ids.start_button.disabled = False
            self.root.get_screen('trading').ids.stop_button.disabled = True
            self.stop_ellipsis_animation()
            self.root.get_screen('trading').ids.countdown_label.text = "MetaTrader5"
            self.root.current = 'SFX Login'

    def clear_log(self):
        self.root.get_screen('trading').ids.log_box.clear_widgets()

    def update_log(self, message):
        label = MDLabel(text=message, halign='center', size_hint_y=None, height=self.theme_cls.standard_increment)
        self.root.get_screen('trading').ids.log_box.add_widget(label)

    def update_trade_status(self, message):
        self.root.get_screen('trading').ids.trade_status_label.text = message

    def get_current_rates(self, symbol, timeframe, count=20):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) < count:
            logging.error("Failed to retrieve candle data for %s", symbol)
            self.update_log(f"Failed to retrieve candle data for {symbol}")
            self.stop_ellipsis_animation()
            return None
        return rates

    def trade(self, symbol):
        bullish_points, bearish_points = self.check_bullish_bearish_live(symbol)
        current_time = datetime.now()

        if bullish_points and datetime.fromtimestamp(bullish_points[0]['time']).date() == current_time.date():
            self.execute_trade(symbol, "buy")

        if bearish_points and datetime.fromtimestamp(bearish_points[0]['time']).date() == current_time.date():
            self.execute_trade(symbol, "sell")

    def check_bullish_bearish_live(self, symbol):
        rates = self.get_current_rates(symbol, mt5.TIMEFRAME_M15, 50)
        if rates is None:
            return [], []

        prev2, prev1, current = rates[-3], rates[-2], rates[-1]

        bullish_points = []
        bearish_points = []

        # Refined Bullish condition
        if prev1['close'] > prev1['open'] and current['close'] > prev1['close'] and current['open'] < prev1['close']:
            bullish_points.append(current)

        # Refined Bearish condition
        if prev1['close'] < prev1['open'] and current['close'] < prev1['close'] and current['open'] > prev1['close']:
            bearish_points.append(current)

        return bullish_points, bearish_points

    def execute_trade(self, symbol, action):
        if self.trades_executed >= self.max_trades:
            logging.info("Maximum trades executed. Exiting.")
            self.update_trade_status("Maximum trades executed.")
            return

        if action not in ["buy", "sell"]:
            logging.error("Invalid trade action")
            self.update_trade_status("Invalid trade action")
            self.stop_ellipsis_animation()
            return

        tick = mt5.symbol_info_tick(symbol)
        if not tick or not tick.bid or not tick.ask:
            logging.error("Failed to get tick for symbol %s", symbol)
            self.update_trade_status("Failed to get tick for symbol.")
            self.stop_ellipsis_animation()
            return

        price = tick.ask if action == "buy" else tick.bid

        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logging.error("Failed to get symbol info for %s", symbol)
            self.update_trade_status("Failed to get symbol info.")
            self.stop_ellipsis_animation()
            return

        # Ensure volume is within the allowed range
        min_volume = symbol_info.volume_min
        max_volume = symbol_info.volume_max
        volume_step = symbol_info.volume_step

        # Adjust the volume according to user input and volume step
        volume = max(min(self.volume, max_volume), min_volume)
        rounded_volume = round(volume / volume_step) * volume_step
        if rounded_volume < min_volume:
            rounded_volume = min_volume

        logging.info("Executing %s %s %s at %s with volume %s", action, rounded_volume, symbol, price, volume)
        self.update_log(f"Executing {action} {rounded_volume} {symbol} at {price}")
        self.stop_ellipsis_animation()

        filling_modes = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
        for filling_mode in filling_modes:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": rounded_volume,
                "type": mt5.ORDER_TYPE_BUY if action == "buy" else mt5.ORDER_TYPE_SELL,
                "price": price,
                "deviation": 10,
                "magic": 234000,
                "comment": "SlingShotFX",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_mode,
            }

            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.trades_executed += 1
                logging.info("Order executed: %s %s %s at %s", action, rounded_volume, symbol, price)
                self.update_trade_status(f"Order executed: {action} {rounded_volume} {symbol} at {price}")
                self.update_log(f"Order executed: {action} {rounded_volume} {symbol} at {price}")
                self.stop_ellipsis_animation()  # Stop ellipsis animation on successful order execution
                return
            else:
                logging.error("Failed to send order with filling mode %s: %s, %s", filling_mode, result.retcode, result.comment)
                self.update_log(f"Order failed with filling mode {filling_mode}: {result.comment}")
                self.stop_ellipsis_animation()

if __name__ == '__main__':
    Window.size = (360, 640)
    SlingShotFX().run()
