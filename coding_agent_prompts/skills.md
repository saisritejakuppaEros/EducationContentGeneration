# Development Guidelines

## Project Structure

Follow the project structure strictly.

### Scripts

* All executable Python code **must** be placed inside the `scripts/` directory.
* Use clear, descriptive filenames that reflect the purpose of each script.
* Do not place Python files anywhere else in the repository.

### Documentation

* Store all documentation inside the `docs/` directory.
* Create one concise Markdown file for each module or major component.
* Each document should briefly describe:

  * What the module does.
  * Its primary purpose.
  * Important inputs.
  * Important outputs (if applicable).

Keep documentation short and practical. Avoid lengthy technical explanations unless specifically requested.

### Outputs

* Every script must save its generated outputs under:

```
output/<sub_module_name>/
```

Examples:

```
output/depth_estimation/
output/object_reconstruction/
output/scene_reconstruction/
output/evaluation/
```

Never write generated files outside the corresponding `output/` subdirectory.

---

# Coding Principles

* Prioritize **working, maintainable code** over excessive documentation.
* Keep implementations simple and easy to understand.
* Avoid unnecessary abstractions.
* Avoid large docstrings unless they explain non-obvious logic.
* Write clean, modular, and reusable code.
* Use descriptive variable and function names.
* Keep scripts focused on a single responsibility whenever possible.

---

# Repository Rules

* Python code belongs only inside `scripts/`.
* Documentation belongs only inside `docs/`.
* Generated files belong only inside `output/<sub_module_name>/`.
* Do not create additional folders unless explicitly required.
* Avoid modifying the project structure unless requested.

---

# Development Style

When implementing new functionality:

1. Write the working code first.
2. Keep the implementation modular.
3. Add a short documentation file in `docs/`.
4. Save all generated artifacts in the appropriate `output/` directory.
5. Avoid unnecessary complexity and over-engineering.

The objective is to build a clean, organized, and maintainable codebase that is easy to navigate, extend, and debug.
