import json

class cachev0:
    def __init__(self, jsonFileName: str):
        self.storage = {}
        self.changesToWrite = False
        if jsonFileName != "":
            with open(jsonFileName, "r") as f:
                self.storage = json.load(f)
        else:
            self.storage = dict()

def digitsToEmoji(digit: str):
    emojis = ("0⃣", "1⃣","2⃣","3⃣","4⃣","5⃣","6⃣","7⃣","8⃣","9⃣")
    answer = ""
    for d in digit:
        answer += emojis[int(d)]    
    return answer

def discountToEmoji(discount: str):
    return digitsToEmoji(discount[1:-1])