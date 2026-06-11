.PHONY: doctor quick-check full-check validate-configs validate-architecture kernel-smoke generate-docs

doctor:
	bash scripts/agent/doctor.sh

quick-check:
	bash scripts/agent/quick-check.sh

full-check:
	bash scripts/agent/full-check.sh

validate-configs:
	bash scripts/agent/validate-configs.sh

validate-architecture:
	bash scripts/agent/validate-architecture.sh

kernel-smoke:
	bash scripts/agent/run-kernel-smoke.sh

generate-docs:
	bash scripts/agent/generate-docs.sh
