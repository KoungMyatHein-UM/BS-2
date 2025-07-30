import importlib
import sys
import time
import traceback
from app.core import feature_interface

class FeatureManager:
    def __init__(self, feature_definitions):
        self.features = self.load_features(feature_definitions)

    def load_features(self, feature_definitions):
        loaded_features = {}
        print("[FeatureManager] Loading features...")

        for feature in feature_definitions:
            feature_name = feature
            feature_display_name = feature_definitions[feature]['display_name']
            feature_version = feature_definitions[feature]['version']
            feature_description = feature_definitions[feature]['description']
            feature_icon = feature_definitions[feature]['icon']
            module_path = f"features.{feature_name}.{feature_version}.{feature_name}"

            print(f"  → [{feature_name}] Loading from {module_path}...", end=" ", flush=True)

            start_time = time.time()
            try:
                module = importlib.import_module(module_path)
            except ModuleNotFoundError:
                print("❌ Failed")
                raise Exception(f"Module not found: {module_path}")

            if not hasattr(module, "register"):
                print("❌ Failed")
                raise Exception(f"Feature module missing register(): {module_path}")

            try:
                instance = module.register()
            except Exception as e:
                print("❌ Failed during register()")
                traceback.print_exc()
                print(Exception(f"Error during feature registration: {module_path}\n{e}"), file=sys.stderr)
                continue

            if not isinstance(instance, feature_interface.BaseFeature):
                print("❌ Failed")
                raise Exception(f"register() did not return BaseFeature: {module_path}")

            elapsed = time.time() - start_time
            print(f"✅ Done ({elapsed:.2f}s)")

            loaded_features[feature_name] = {
                "instance": instance,
                "version": feature_version,
                "display_name": feature_display_name,
                "description": feature_description,
                "icon": feature_icon,
            }

        print(f"[FeatureManager] Loaded {len(loaded_features)} feature(s).")
        return loaded_features

    def get_feature(self, feature_name):
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
