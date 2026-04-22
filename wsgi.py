import os
from recepti.recipe_store import RecipeStore
from recepti.web_app import create_app

data_dir = os.environ.get("RECEPTI_DATA_DIR", "data")
store = RecipeStore(
    os.path.join(data_dir, "recipes.json"),
    extra_sources=[
        os.path.join(data_dir, "croatian_recipes.json"),
        os.path.join(data_dir, "expanded_recipes.json"),
    ],
)
app = create_app(store)