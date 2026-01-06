from dataclasses import dataclass
from typing import Dict

@dataclass
class User:
    username: str
    password: str  
    role: str      

USERS: Dict[str, User] = {
    "student1": User(username="student1", password="1234", role="student"),
    "instructor1": User(username="instructor1", password="1234", role="instructor"),
}
