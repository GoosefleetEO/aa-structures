help:	
	@echo "Makefile for aa-structures"	

makemessages:
	cd structures && \
	django-admin makemessages -l de --ignore 'build/*' && \
	django-admin makemessages -l es --ignore 'build/*' && \
	django-admin makemessages -l zh_Hans --ignore 'build/*'

tx_push:
	tx push --source

compilemessages:	
	cd structures && \
	django-admin compilemessages -l de  && \
	django-admin compilemessages -l es  && \
	django-admin compilemessages -l zh_Hans

coverage:
	coverage run ../myauth/manage.py test structures --keepdb --failfast --debug-mode && coverage html && coverage report
	