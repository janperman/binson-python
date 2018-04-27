import struct
import six # Used for supporting python 2 and 3 string types
import sys

# Workaround for python 2 and 3 support
if sys.version_info > (3,):
	intType = int
	stringBytes = lambda x: bytes(x.encode('utf8'))
else:
	intType = long
	stringBytes = lambda x: bytes(x)

class BinsonException(Exception):
	pass

class BinsonArray:
	pass
class BinsonParser:

	@staticmethod
	def fromBytes(rawBytes):
		b = BinsonParser(rawBytes)
		obj = b.__parseObject()
		diff = b.getDiff()
		if diff is not 0:
			raise BinsonException('Invalid data (%d bytes) after binson object.' % diff)
		return obj

	def __init__(self, rawBytes):
		if not type(rawBytes) is bytearray:
			try:
				rawBytes = bytearray(rawBytes)
			except:
				raise BinsonException('Input is not or could not be converted to bytearray.')

		if len(rawBytes) < 2:
			raise BinsonException('Length of input buffer must be least 2 bytes long.')

		self.rawBytes = rawBytes
		self.offset = 0

	def getDiff(self):
		return self.offset - len(self.rawBytes)

	def __parseObject(self):
		if self.rawBytes[self.offset] != 0x40:
			raise BinsonException('Bad first byte in object (0x%02x), expected 0x40.' % self.rawBytes[self.offset])

		self.offset += 1
		prevName = ''
		content = {}

		while self.offset < len(self.rawBytes):

			if self.rawBytes[self.offset] == 0x41:
				self.offset += 1
				return Binson(content)

			if self.rawBytes[self.offset] not in [0x14,0x15,0x16]:
				raise BinsonException('Bad byte (0x%02x) at offset %d, expected stringLen.' % (self.rawBytes[self.offset], self.offset))

			valueParser = self.valueParsers[self.rawBytes[self.offset]]
			fieldName = valueParser[0](self, *valueParser[1])

			if fieldName <= prevName:
				raise BinsonException('Fields not in lexicographical order when parsing. Current: %s, previous: %s' % (fieldName, prevName))

			if not self.rawBytes[self.offset] in self.valueParsers:
				raise BinsonException('Unsupported type (0x%02x) at offset %d.' % (self.rawBytes[self.offset], self.offset))
			valueParser = self.valueParsers[self.rawBytes[self.offset]]

			content[fieldName] = valueParser[0](self, *valueParser[1])
			prevName = fieldName

	def __parseString(self, lengthSize, unpack):
		try:
			return self.__parseBytes(lengthSize, unpack).decode('utf8')
		except:
			raise BinsonException('Invalid utf8 byte stream.')

	def __parseBytes(self, lengthSize, unpack):
		self.offset += 1
		if self.offset + lengthSize >= len(self.rawBytes):
			raise BinsonException('Buffer to small to parse size of bytes.')
		bytesLen, = struct.unpack_from(unpack, self.rawBytes, self.offset)
		if bytesLen <= 0:
			raise BinsonException('Bad length (%d)' % bytesLen)
		self.offset += lengthSize
		if self.offset + bytesLen >= len(self.rawBytes):
			raise BinsonException('Buffer to small to parse bytes.')
		bytesVal = self.rawBytes[self.offset:self.offset+bytesLen]
		self.offset += bytesLen
		return bytesVal

	def __parseArray(self):
		listVal = []
		self.offset += 1
		while self.offset < len(self.rawBytes) - 1:
			if self.rawBytes[self.offset] == 0x43:
				self.offset += 1
				return listVal
			try:
				valueParser = self.valueParsers[self.rawBytes[self.offset]]
			except:
				raise BinsonException('Unsupported type (0x%02x) at offset %d.' % (self.rawBytes[self.offset], self.offset))
			listVal.append(valueParser[0](self, *valueParser[1]))

	def __parseBool(self):
		self.offset += 1
		return self.rawBytes[self.offset - 1] == 0x44

	def __parseFloat(self):
		self.offset += 1
		if self.offset + 8 >= len(self.rawBytes):
			raise BinsonException('Buffer to small to parse float.')
		floatVal = struct.unpack_from('<d', self.rawBytes, self.offset)
		self.offset += 8
		return floatVal

	def __parseInt(self, lengthSize, unpack):
		self.offset += 1
		if self.offset + lengthSize >= len(self.rawBytes):
			raise BinsonException('Buffer to small to parse integer.')
		intVal, = struct.unpack_from(unpack, self.rawBytes, self.offset)
		intVal = intType(intVal)
		self.offset += lengthSize
		return intVal

	valueParsers = {
		0x40: (__parseObject, ()),
		0x42: (__parseArray, ()),
		0x44: (__parseBool, ()),
		0x45: (__parseBool, ()),
		0x46: (__parseFloat, ()),
		0x10: (__parseInt, (1, '<b')),
		0x11: (__parseInt, (2, '<h')),
		0x12: (__parseInt, (4, '<i')),
		0x13: (__parseInt, (8, '<q')),
		0x14: (__parseString, (1, '<b')),
		0x15: (__parseString, (2, '<h')),
		0x16: (__parseString, (4, '<i')),
		0x18: (__parseBytes, (1, '<b')),
		0x19: (__parseBytes, (2, '<h')),
		0x20: (__parseBytes, (4, '<i'))
	}

class Binson():

	def __init__(self, dict = {}):
		self.dict = dict

	def __checkKeyAndTypeAndReturn(self, field, expectedType):
		if not field in self.dict:
			raise BinsonException('Binson object does not contain field name "%s"' % field)
		if not isinstance(self.dict[field], expectedType):
			raise BinsonException('Field name "%s" does not contain expected field' % field)
		return self.dict[field]

	def get(self, field):
		if not field in self.dict:
			raise BinsonException('Binson object does not contain field name "%s"' % field)
		return self.dict[field]

	def keys(self):
		return self.dict.keys()

	def getObject(self, field):
		return self.__checkKeyAndTypeAndReturn(field, Binson)

	def getString(self, field):
		return self.__checkKeyAndTypeAndReturn(field, six.string_types)

	def getBool(self, field):
		return self.__checkKeyAndTypeAndReturn(field, bool)

	def getInteger(self, field):
		return self.__checkKeyAndTypeAndReturn(field, intType)

	def getArray(self, field):
		return self.__checkKeyAndTypeAndReturn(field, list)

	def getBytes(self, field):
		return self.__checkKeyAndTypeAndReturn(field, bytearray)

	def getFloat(self, field):
		return self.__checkKeyAndTypeAndReturn(field, float)

	@staticmethod
	def fromBytes(rawBytes):
		return BinsonParser.fromBytes(rawBytes)

	def toBytes(self):
		return BinsonWriter(self).toBytes()

	def __str__(self):
		return 'Binson'

class BinsonWriter:
	def __init__(self, obj):
		self.obj = obj
	def toBytes(self):
		return self.__writeObj(self.obj)

	def __writeObj(self, obj):
		rawBytes = bytearray()
		rawBytes.append(0x40)
		for key in sorted(obj.keys()):
			rawBytes += self.__writeString(key)
			valueType = obj.get(key).__class__.__name__
			if not valueType in self.valueWriters:
				raise BinsonException('Cannot write type %s into a binson object.' % valueType)
			rawBytes += self.valueWriters[valueType](self, obj.get(key))
		rawBytes.append(0x41)
		return rawBytes

	def __writeInt(self, intVal):
		packVal = '<b'
		typeVal = 0x10
		if intVal < -(2**7) or intVal > (2**7 - 1):
			packVal = '<h'
			typeVal = 0x11
		if intVal < -(2**15) or intVal > (2**15 - 1):
			packVal = '<i'
			typeVal = 0x12
		if intVal < -(2**31) or intVal > (2**31 - 1):
			packVal = '<q'
			typeVal = 0x13
		rawBytes = bytearray()
		rawBytes.append(typeVal)
		intBytes = struct.pack(packVal, intVal)
		rawBytes += intBytes
		return rawBytes
	def __writeBytes(self, bytesVal):
		rawBytes = bytearray()
		typeVal = 0x18
		packVal = '<b'
		if len(bytesVal) > 2**7 - 1:
			typeVal = 0x19
			packVal = '<h'
		if len(bytesVal) > 2**15 - 1:
			typeVal = 0x1a
			packVal = '<i'
		rawBytes.append(typeVal)
		rawBytes += struct.pack(packVal, len(bytesVal))
		rawBytes += bytesVal
		return rawBytes
	def __writeString(self, stringVal):
		rawBytes = bytearray()
		typeVal = 0x14
		packVal = '<b'
		if len(stringVal) > 2**7 - 1:
			typeVal = 0x15
			packVal = '<h'
		if len(stringVal) > 2**15 - 1:
			typeVal = 0x16
			packVal = '<i'
		rawBytes.append(typeVal)
		rawBytes += struct.pack(packVal, len(stringVal))
		rawBytes += stringBytes(stringVal)
		return rawBytes
	def __writeBinson(self, objVal):
		return BinsonWriter(objVal).toBytes()
	def __writeBool(self, boolVal):
		if boolVal:
			return bytearray([0x44])
		return bytearray([0x45])
	def __writeList(self, listVal):
		rawBytes = bytearray()
		rawBytes.append(0x42)
		for val in listVal:
			valueType = val.__class__.__name__
			if not valueType in self.valueWriters:
				raise BinsonException('Cannot write type %s into a binson object.' % valueType)
			rawBytes += self.valueWriters[valueType](self, val)
		rawBytes.append(0x43)
		return rawBytes

	valueWriters = {
		'long': __writeInt,
		'int': __writeInt,
		'bytearray': __writeBytes,
		'unicode': __writeString,
		'str': __writeString,
		'Binson': __writeObj,
		'bool': __writeBool,
		'list': __writeList
	}