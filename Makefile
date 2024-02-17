.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "Welcome to ToGif example. Please use \`make <target>\` where <target> is one of"
	@echo " "
	@echo "  Next commands are only for dev environment with nextcloud-docker-dev!"
	@echo "  They should run from the host you are developing on(with activated venv) and not in the container with Nextcloud!"
	@echo "  "
	@echo "  build-push        build image and upload to ghcr.io"
	@echo "  "
	@echo "  run27             install ToGif for Nextcloud 27"
	@echo "  run28             install ToGif for Nextcloud 28"
	@echo "  run               install ToGif for Nextcloud Last"
	@echo "  "
	@echo "  For development of this example use PyCharm run configurations. Development is always set for last Nextcloud."
	@echo "  First run 'to_gif_example' and then 'make registerX', after that you can use/debug/develop it and easy test."
	@echo "  "
	@echo "  register27        perform registration of running 'to_gif_example' into 'manual_install' deploy daemon."
	@echo "  register28        perform registration of running 'to_gif_example' into 'manual_install' deploy daemon."
	@echo "  register          perform registration of running 'to_gif_example' into 'manual_install' deploy daemon."

.PHONY: build-push
build-push:
	docker login ghcr.io
	docker buildx build --push --platform linux/arm64/v8,linux/amd64 --tag ghcr.io/cloud-py-api/to_gif_example:1.3.0 --tag ghcr.io/cloud-py-api/to_gif_example:latest .

.PHONY: run27
run27:
	docker exec master-stable27-1 sudo -u www-data php occ app_api:app:unregister to_gif_example --silent || true
	docker exec master-stable27-1 sudo -u www-data php occ app_api:app:register to_gif_example \
		--force-scopes \
		--info-xml https://raw.githubusercontent.com/cloud-py-api/to_gif_example/v1.2.0/appinfo/info.xml

.PHONY: run28
run28:
	docker exec master-stable28-1 sudo -u www-data php occ app_api:app:unregister to_gif_example --silent || true
	docker exec master-stable28-1 sudo -u www-data php occ app_api:app:register to_gif_example \
		--force-scopes \
		--info-xml https://raw.githubusercontent.com/cloud-py-api/to_gif_example/main/appinfo/info.xml

.PHONY: run
run:
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:unregister to_gif_example --silent || true
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:register to_gif_example \
		--force-scopes \
		--info-xml https://raw.githubusercontent.com/cloud-py-api/to_gif_example/v1.2.0/appinfo/info.xml

.PHONY: register27
register27:
	docker exec master-stable27-1 sudo -u www-data php occ app_api:app:unregister to_gif_example --silent || true
	docker exec master-stable27-1 sudo -u www-data php occ app_api:app:register to_gif_example manual_install --json-info \
  "{\"id\":\"to_gif_example\",\"name\":\"to_gif_example\",\"daemon_config_name\":\"manual_install\",\"version\":\"1.0.0\",\"secret\":\"12345\",\"port\":10040,\"scopes\":[\"FILES\", \"NOTIFICATIONS\"],\"system\":0}" \
  --force-scopes --wait-finish

.PHONY: register28
register28:
	docker exec master-stable28-1 sudo -u www-data php occ app_api:app:unregister to_gif_example --silent || true
	docker exec master-stable28-1 sudo -u www-data php occ app_api:app:register to_gif_example manual_install --json-info \
  "{\"id\":\"to_gif_example\",\"name\":\"to_gif_example\",\"daemon_config_name\":\"manual_install\",\"version\":\"1.0.0\",\"secret\":\"12345\",\"port\":10040,\"scopes\":[\"FILES\", \"NOTIFICATIONS\"],\"system\":0}" \
  --force-scopes --wait-finish

.PHONY: register
register:
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:unregister to_gif_example --silent || true
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:register to_gif_example manual_install --json-info \
  "{\"id\":\"to_gif_example\",\"name\":\"to_gif_example\",\"daemon_config_name\":\"manual_install\",\"version\":\"1.0.0\",\"secret\":\"12345\",\"port\":10040,\"scopes\":[\"FILES\", \"NOTIFICATIONS\"],\"system\":0}" \
  --force-scopes --wait-finish
