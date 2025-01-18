from pydantic import BaseModel
from random import shuffle
from sqlmodel import SQLModel
class Car(SQLModel):
    year: str
    model: str
    age: int

cars = [None,Car(year = "02102000", model = "toyota", age = 11)]
shuffle(cars)

if cars[0] == None:
    print(cars[0], "это None")
else:
    print(cars[0])