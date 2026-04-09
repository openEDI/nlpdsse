
from pydantic import BaseModel


class StaticInputs(BaseModel):
	start_date:str | None = None
	run_freq_sec:int = 900
	start_time_index:int = 0
	number_of_timesteps:int = 8
	broker_address:str = "localhost"
	port:int = 23404

class InputMapping(BaseModel):
	powers_real: str
	powers_imaginary: str
	topology: str
