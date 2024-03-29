.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "Welcome to ExtractArchivesNCPyAPI example. Please use \`make <target>\` where <target> is one of"
	@echo " "
	@echo "  Next commands are only for dev environment with nextcloud-docker-dev!"
	@echo "  They should run from the host you are developing on(with activated venv) and not in the container with Nextcloud!"
	@echo "  "
	@echo "  build-push        build image and upload to ghcr.io"
	@echo "  "
	@echo "  run27             install ExtractArchivesNCPyAPI for Nextcloud 27"
	@echo "  run28             install ExtractArchivesNCPyAPI for Nextcloud 28"
	@echo "  run               install ExtractArchivesNCPyAPI for Nextcloud Last"
	@echo "  "
	@echo "  For development of this example use PyCharm run configurations. Development is always set for last Nextcloud."
	@echo "  First run 'extract_archives_nc_py_api' and then 'make registerX', after that you can use/debug/develop it and easy test."
	@echo "  "
	@echo "  register27        perform registration of running 'extract_archives_nc_py_api' into 'manual_install' deploy daemon."
	@echo "  register28        perform registration of running 'extract_archives_nc_py_api' into 'manual_install' deploy daemon."
	@echo "  register          perform registration of running 'extract_archives_nc_py_api' into 'manual_install' deploy daemon."

.PHONY: build-push
build-push:
	docker login ghcr.io
	docker buildx build --push --platform linux/amd64 --tag ghcr.io/valdearg/extract_archives_nc_py_api:0.0.1 --tag ghcr.io/valdearg/extract_archives_nc_py_api:latest .

.PHONY: run27
run27:
	docker exec master-stable27-1 sudo -u www-data php occ app_api:app:unregister extract_archives_nc_py_api --silent || true
	docker exec master-stable27-1 sudo -u www-data php occ app_api:app:register extract_archives_nc_py_api \
		--force-scopes \
		--info-xml https://raw.githubusercontent.com/valdearg/extract_archives_nc_py_api/v1.2.0/appinfo/info.xml

.PHONY: run28
run28:
	docker exec master-stable28-1 sudo -u www-data php occ app_api:app:unregister extract_archives_nc_py_api --silent || true
	docker exec master-stable28-1 sudo -u www-data php occ app_api:app:register extract_archives_nc_py_api \
		--force-scopes \
		--info-xml https://raw.githubusercontent.com/valdearg/extract_archives_nc_py_api/main/appinfo/info.xml

.PHONY: run
run:
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:unregister extract_archives_nc_py_api --silent || true
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:register extract_archives_nc_py_api \
		--force-scopes \
		--info-xml https://raw.githubusercontent.com/valdearg/extract_archives_nc_py_api/v1.2.0/appinfo/info.xml

.PHONY: register27
register27:
	docker exec master-stable27-1 sudo -u www-data php occ app_api:app:unregister extract_archives_nc_py_api --silent || true
	docker exec master-stable27-1 sudo -u www-data php occ app_api:app:register extract_archives_nc_py_api manual_install --json-info \
  "{\"id\":\"extract_archives\",\"name\":\"extract_archives\",\"daemon_config_name\":\"manual_install\",\"version\":\"1.0.0\",\"secret\":\"12345\",\"port\":10040,\"scopes\":[\"FILES\", \"NOTIFICATIONS\"],\"system\":0}" \
  --force-scopes --wait-finish

.PHONY: register28
register28:
	docker exec master-stable28-1 sudo -u www-data php occ app_api:app:unregister extract_archives_nc_py_api --silent || true
	docker exec master-stable28-1 sudo -u www-data php occ app_api:app:register extract_archives_nc_py_api manual_install --json-info \
  "{\"id\":\"extract_archives\",\"name\":\"extract_archives\",\"daemon_config_name\":\"manual_install\",\"version\":\"1.0.0\",\"secret\":\"12345\",\"port\":10040,\"scopes\":[\"FILES\", \"NOTIFICATIONS\"],\"system\":0}" \
  --force-scopes --wait-finish

.PHONY: register
register:
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:unregister extract_archives_nc_py_api --silent || true
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:register extract_archives_nc_py_api manual_install --json-info \
  "{\"id\":\"extract_archives\",\"name\":\"extract_archives\",\"daemon_config_name\":\"manual_install\",\"version\":\"1.0.0\",\"secret\":\"12345\",\"port\":10040,\"scopes\":[\"FILES\", \"NOTIFICATIONS\"],\"system\":0}" \
  --force-scopes --wait-finish

.PHONY: run27local
run27local:
	sudo -u www-data php8.2 /var/www/nextcloud/occ app_api:app:unregister extract_archives_nc_py_api --silent || true
	sudo -u www-data php8.2 /var/www/nextcloud/occ app_api:app:register extract_archives_nc_py_api \
		--force-scopes \
		--info-xml https://raw.githubusercontent.com/valdearg/extract_archives_nc_py_api/v1.2.0/appinfo/info.xml

.PHONY: run28local
run28local:
	sudo -u www-data php8.2 /var/www/nextcloud/occ app_api:app:unregister extract_archives_nc_py_api --silent || true
	sudo -u www-data php8.2 /var/www/nextcloud/occ app_api:app:register extract_archives_nc_py_api \
		--force-scopes \
		--info-xml https://raw.githubusercontent.com/valdearg/extract_archives_nc_py_api/main/appinfo/info.xml

.PHONY: runlocal
runlocal:
	sudo -u www-data php8.2 /var/www/nextcloud/occ app_api:app:unregister extract_archives_nc_py_api --silent || true
	sudo -u www-data php8.2 /var/www/nextcloud/occ app_api:app:register extract_archives_nc_py_api \
		--force-scopes \
		--info-xml https://raw.githubusercontent.com/valdearg/extract_archives_nc_py_api/v1.2.0/appinfo/info.xml