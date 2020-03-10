help:	
	@echo "Makefile for aa-structures"	

makemessages:
	django-admin makemessages -l de --ignore 'build/*'

tx_upload:
	tx push --source

compilemessages:
	rm -rf .tox
	django-admin compilemessages
