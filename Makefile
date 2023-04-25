appname = aa-structures
package = structures

help:
	@echo "Makefile for $(appname)"

makemessages:
	cd $(package) && \
	django-admin makemessages \
		-l de \
		-l en \
		-l es \
		-l fr_FR \
		-l it_IT \
		-l ja \
		-l ko_KR \
		-l ru \
		-l uk \
		-l zh_Hans \
		--keep-pot \
		--ignore 'build/*'

tx_push:
	tx push --source

tx_pull:
	tx pull -f

compilemessages:
	cd $(package) && \
	django-admin compilemessages \
		-l de \
		-l en \
		-l es \
		-l fr_FR \
		-l it_IT \
		-l ja \
		-l ko_KR \
		-l ru \
		-l uk \
		-l zh_Hans

coverage:
	coverage run ../myauth/manage.py test --keepdb && coverage html && coverage report -m

test:
	# runs a full test incl. re-creating of the test DB
	python ../myauth/manage.py test $(package) --failfast --debug-mode -v 2

pylint:
	pylint --load-plugins pylint_django $(package)

check_complexity:
	flake8 $(package) --max-complexity=10

flake8:
	flake8 $(package) --count

graph_models:
	python ../myauth/manage.py graph_models $(package) --arrow-shape normal -o $(appname)_models.png

create_testdata:
	python ../myauth/manage.py test $(package).tests.testdata.create_eveuniverse --keepdb -v 2
