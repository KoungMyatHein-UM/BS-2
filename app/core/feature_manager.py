import importlib
import time
import traceback
from app.core import feature_interface

# HELPER METHODS
def apply_defaults(config, defaults):
    for key, value in defaults.items():
        config.setdefault(key, value)
    return config

def apply_overrides(config, overrides):
    for key, value in overrides.items():
        if key in config:
            config[key] = value
    return config
# ==================================

# TODO: Pass plugin debug flag
# TODO: Pass plugin debug flag

class FeatureManager:
    def __init__(self, defaults, feature_definitions):
        self.features = self.load_features(defaults, feature_definitions)

    def shutdown(self):
        print("[FeatureManager] Shutting down features...")
        for feature in self.features.values():
            shutdown_fn = feature.get("shutdown")
            if callable(shutdown_fn):
                print(f"[FeatureManager] Shutting down {feature['display_name']}...")
                shutdown_fn()

    def load_features(self, defaults, feature_definitions):

        loaded_features = {}
        failures = 0
        scanned = 0
        disabled = 0

        print("[FeatureManager] Loading features...")
        print(f"[FeatureManager] {len(feature_definitions)} feature(s) defined.")

        for feature in feature_definitions:
            scanned += 1

            feature_name = feature

            feature_config = apply_defaults({}, defaults)
            feature_config = apply_overrides(feature_config, feature_definitions[feature])

            feature_enabled = feature_config['enabled']
            feature_cached = feature_config['cached']
            feature_display_name = feature_config['display_name']
            feature_version = feature_config['version']
            feature_description = feature_config['description']
            feature_icon = feature_config['icon']

            # configure module path
            module_path = f"features.{feature_name}.{feature_version}.{feature_name}"

            print(f"  → [{feature_name}] Loading {scanned}/{len(feature_definitions)} from {module_path}...")

            # 1. Check if feature is enabled
            if not feature_enabled:
                print(f"    → ⚠️ Feature is disabled. Skipping...", flush=True)
                disabled += 1
                continue

            start_time = time.time()

            # 1. Dynamically import the feature module using the configured path
            try:
                module = importlib.import_module(module_path)
            # 1.1. If the module cannot be found
            except ModuleNotFoundError:
                print(f"    → ❌ Failed: Module not found: {module_path}")
                failures += 1
                continue

            # 2. Verify module exposes registration method
            if not hasattr(module, "register"):
                print(f"    → ❌ Failed: Feature module missing register(): {module_path}")
                failures += 1
                continue

            # 3. Call registration method and hold instance data
            try:
                module_instance_data = module.register()
            # 3.1. If module registration fails
            except Exception as e:
                print("    → ❌ Failed during register()")
                traceback.print_exc()
                print(Exception(f"    → ❌ Error during feature registration: {module_path}\n{e}"))
                failures += 1
                continue

            # 3.2. Verify registration data
            if not isinstance(module_instance_data, dict):
                print(Exception(f"    → ❌ Bad registration: required dict, got {type(module_instance_data)} instead."))
                failures += 1
                continue


            # 4. Verify that module is an instance of contract
            instance = module_instance_data.get("instance")
            if not isinstance(instance, feature_interface.BaseFeature):
                print(f"    → ❌ Failed: register() did not return BaseFeature: {module_path}")
                failures += 1
                continue

            # 5. Check if module has an optional self-test method
            self_test = module_instance_data.get("self_test")
            # 5.1. Perform self-test if exists
            if callable(self_test):
                result = self_test()
                if result:
                    print(f"    → ✅ Self-test passed!")
                else:
                    print(f"    → ❌ Self-test failed! Skipping feature...")
                    failures += 1
                    continue
            else:
                print(f"    → ⚠️ No self-test defined. Optional self-testing is recommended!")


            elapsed = time.time() - start_time
            print(f"    → ✅ Done ({elapsed:.2f}s)")

            # 5. Store with other features
            loaded_features[feature_name] = {
                "instance": instance,
                "shutdown": module_instance_data.get("shutdown"),
                "version": feature_version,
                "display_name": feature_display_name,
                "description": feature_description,
                "icon": feature_icon,
            }

        print(f"[FeatureManager] Scanned:\t{scanned} feature(s).")
        print(f"[FeatureManager] Disabled:\t{disabled} feature(s).")
        print(f"[FeatureManager] Failed:\t{failures} feature(s).")
        print(f"[FeatureManager] Loaded:\t{len(loaded_features)} feature(s).")
        return loaded_features

    def __get_feature(self, feature_name: str) -> feature_interface.BaseFeature:
        feature = self.features.get(feature_name)
        if not feature:
            raise Exception(f"Feature '{feature_name}' not found")
        return feature["instance"]

    def get_available_features(self):
        return {
            name: {
                "version": data["version"],
                "display_name": data["display_name"]
            }
            for name, data in self.features.items()
        }

    def invoke_feature(self, feature_name: str, params):

        feature = self.__get_feature(feature_name)
        response = feature.run(params)

        return response