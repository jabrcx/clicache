if False:
	import logging
	for name in ('clicache',):
		logger = logging.getLogger(name)
		logger.setLevel(logging.DEBUG)
		handler = logging.StreamHandler()
		formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(name)s: %(message)s')
		handler.setFormatter(formatter)
		logger.addHandler(handler)
