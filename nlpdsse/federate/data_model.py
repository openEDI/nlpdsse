from typing import Dict, List

from pydantic import BaseModel


class YBus(BaseModel):
	r: List[int]
	c: List[int]
	vr: List[float]
	vi: List[float]


class BranchFlow(BaseModel):
	y: YBus
	nodeInd: List[int]
	nodeOrder: List[str]


class MeasurementData(BaseModel):
	pinj: List[float]
	qinj: List[float]
	sinj_nodeOrder: List[str]
	sflow_real: List[float] | None = None
	sflow_imag: List[float] | None = None
	sflow_nodeOrder: List[str] | None = None


class NodeOrder(BaseModel):
	names:List[str]
	name2ind:Dict[str,int]
	ind2name:Dict[int,str]


class DSSEDataModel(BaseModel):
	x0: List[float]
	ybus: YBus
	nodeOrder: NodeOrder
	measurement: MeasurementData
	branch_flow: BranchFlow | None = None
	vm0: List[float]

