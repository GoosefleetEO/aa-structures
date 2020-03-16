help:	
	@echo "Makefile for aa-structures"	

makemessages:
	cd structures && \
	django-admin makemessages -l en --ignore 'build/*' && \
	django-admin makemessages -l de --ignore 'build/*' && \
	django-admin makemessages -l es --ignore 'build/*' && \
	django-admin makemessages -l ko --ignore 'build/*' && \
	django-admin makemessages -l ru --ignore 'build/*' && \
	django-admin makemessages -l zh_Hans --ignore 'build/*'

tx_push:
	tx push --source

tx_pull:
	tx pull -f

compilemessages:	
	cd structures && \
	django-admin compilemessages -l en  && \
	django-admin compilemessages -l de  && \
	django-admin compilemessages -l es  && \
	django-admin compilemessages -l ko  && \
	django-admin compilemessages -l ru  && \
	django-admin compilemessages -l zh_Hans

coverage:
	coverage run ../myauth/manage.py test structures --keepdb --failfast --debug-mode && coverage html && coverage report
	
test:
	# runs a full test incl. re-creating of the test DB
	python ../myauth/manage.py test structures --failfast --debug-mode -v 2

pylint:
	pylint --load-plugins pylint_django structures

check_complexity:
	flake8 structures --max-complexity=10
