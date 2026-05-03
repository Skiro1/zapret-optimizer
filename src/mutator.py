"""Mutation engine for generating new zapret configs from existing ones."""

import copy
import random
from pathlib import Path
from typing import Any

from .config_parser import ZapretConfig, ZapretRule


class ConfigMutator:
    """Generates mutations of zapret configs."""

    # Parameter mutation ranges
    MUTATION_RANGES = {
        "dpi-desync": [
            "fake",
            "multisplit",
            "fakedsplit",
            "disorder",
            "multidisorder",
            "split",
            "fake,multisplit",
            "fake,fakedsplit",
            "fake,multidisorder",
        ],
        "dpi-desync-repeats": list(range(3, 16, 2)),  # 3, 5, 7, 9, 11, 13, 15
        "dpi-desync-split-seqovl": list(range(400, 801, 50)),  # 400-800 step 50
        "dpi-desync-fooling": [
            "",
            "ts",
            "md5sig",
            "badseq",
            "ts,md5sig",
            "ts,badseq",
        ],
        "dpi-desync-cutoff": ["n2", "n3", "n4", "n5"],
        "dpi-desync-split-pos": ["1", "midsld", "1,midsld"],
    }

    # Parameters that can be mutated
    MUTABLE_PARAMS = list(MUTATION_RANGES.keys())

    def __init__(self, seed: int | None = None):
        if seed is not None:
            random.seed(seed)

    def mutate_rule(self, rule: ZapretRule, num_mutations: int = 1) -> ZapretRule:
        """Create a mutated copy of a rule."""
        new_rule = copy.deepcopy(rule)
        params_to_mutate = random.sample(
            self.MUTABLE_PARAMS,
            min(num_mutations, len(self.MUTABLE_PARAMS))
        )

        for param in params_to_mutate:
            if param in new_rule.params:
                new_value = random.choice(self.MUTATION_RANGES[param])
                # Handle empty string as "remove param"
                if new_value == "" and param in new_rule.params:
                    del new_rule.params[param]
                elif new_value != "":
                    new_rule.params[param] = new_value
            else:
                # Add this param if it doesn't exist
                new_value = random.choice(self.MUTATION_RANGES[param])
                if new_value != "":
                    new_rule.params[param] = new_value

        return new_rule

    def mutate_config(
        self,
        config: ZapretConfig,
        num_variants: int = 1,
        mutations_per_variant: int = 1
    ) -> list[ZapretConfig]:
        """Generate mutated variants of a config."""
        variants = []

        for i in range(num_variants):
            new_rules = []
            for rule in config.rules:
                # Only mutate some rules (e.g., TCP rules are more important)
                if rule.filter_type == "tcp" and random.random() < 0.7:
                    new_rule = self.mutate_rule(rule, mutations_per_variant)
                    new_rules.append(new_rule)
                elif rule.filter_type == "udp" and random.random() < 0.3:
                    new_rule = self.mutate_rule(rule, mutations_per_variant)
                    new_rules.append(new_rule)
                else:
                    new_rules.append(copy.deepcopy(rule))

            variant = ZapretConfig(
                name=f"{config.name}_mut_{i+1:03d}",
                rules=new_rules
            )
            variants.append(variant)

        return variants

    def combine_configs(
        self,
        config1: ZapretConfig,
        config2: ZapretConfig,
        num_offspring: int = 1
    ) -> list[ZapretConfig]:
        """Create hybrid configs by combining two parent configs."""
        offspring = []

        for i in range(num_offspring):
            new_rules = []

            # Determine which config contributes more rules
            max_rules = max(len(config1.rules), len(config2.rules))

            for idx in range(max_rules):
                if idx < len(config1.rules) and idx < len(config2.rules):
                    # Both have this rule - randomly pick or mix
                    if random.random() < 0.5:
                        new_rule = copy.deepcopy(config1.rules[idx])
                    else:
                        new_rule = copy.deepcopy(config2.rules[idx])

                    # 20% chance to mutate the combined rule
                    if random.random() < 0.2:
                        new_rule = self.mutate_rule(new_rule, 1)

                    new_rules.append(new_rule)

                elif idx < len(config1.rules):
                    new_rules.append(copy.deepcopy(config1.rules[idx]))
                else:
                    new_rules.append(copy.deepcopy(config2.rules[idx]))

            hybrid = ZapretConfig(
                name=f"hybrid_{config1.name[:10]}_{config2.name[:10]}_{i+1:03d}",
                rules=new_rules
            )
            offspring.append(hybrid)

        return offspring

    def generate_from_best(
        self,
        configs: list[ZapretConfig],
        scores: dict[str, float],
        num_to_generate: int,
        cycle: int
    ) -> list[ZapretConfig]:
        """Generate new configs from best performers."""
        if not configs:
            return []

        # Sort configs by score
        sorted_configs = sorted(
            configs,
            key=lambda c: scores.get(c.name, 0),
            reverse=True
        )

        # Take top performers (top 50%)
        top_count = max(2, len(sorted_configs) // 2)
        top_configs = sorted_configs[:top_count]

        generated = []

        if cycle == 2:
            # Cycle 2: Mutations of top configs
            for i, config in enumerate(top_configs):
                # Generate more variants from better configs
                num_variants = max(1, 3 - i)  # Best gets 3, next gets 2, etc.
                variants = self.mutate_config(config, num_variants=num_variants, mutations_per_variant=2)
                generated.extend(variants)

        elif cycle == 3:
            # Cycle 3: Combinations of top configs
            if len(top_configs) >= 2:
                for i in range(min(num_to_generate, len(top_configs))):
                    # Pair adjacent configs
                    c1 = top_configs[i % len(top_configs)]
                    c2 = top_configs[(i + 1) % len(top_configs)]
                    hybrids = self.combine_configs(c1, c2, num_offspring=1)
                    generated.extend(hybrids)
            else:
                # Fallback to mutations if only 1 top config
                for config in top_configs:
                    variants = self.mutate_config(config, num_variants=2, mutations_per_variant=1)
                    generated.extend(variants)

        # Limit to requested number
        return generated[:num_to_generate]

    def create_variant_bat_files(
        self,
        configs: list[ZapretConfig],
        output_dir: Path,
        start_index: int = 1
    ) -> list[Path]:
        """Write config variants to .bat files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        for i, config in enumerate(configs, start_index):
            # Ensure unique names
            bat_name = f"generated_{i:03d}.bat"
            bat_path = output_dir / bat_name
            config.write_bat(bat_path)
            paths.append(bat_path)

        return paths
