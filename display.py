from RPLCD.i2c import CharLCD

# --- LCD setup ---
lcd = CharLCD('PCF8574', 0x27)

def lcd_init():
    """Clear and initialize LCD"""
    lcd.clear()
    lcd.write_string("Plant Monitor\nSystem Ready")

def update_lcd(line1, line2=""):
    """
    Update LCD with two lines of text
    Example: update_lcd("Soil:Dry Pump:ON", "T:26C H:65%")
    """
    lcd.clear()
    lcd.write_string(line1[:16])   # first line (max 16 chars)
    lcd.crlf()
    lcd.write_string(line2[:16])   # second line (max 16 chars)

def lcd_cleanup():
    lcd.clear()
