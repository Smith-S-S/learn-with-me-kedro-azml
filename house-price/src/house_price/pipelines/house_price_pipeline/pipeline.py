"""
PIPELINE = the wiring diagram that connects the stations (nodes) together.

Each `node(...)` says: "run THIS function, take THESE inputs, and name its
outputs like THIS." Kedro reads the input/output names and automatically works
out the correct order to run everything in. You never call the functions by
hand -- Kedro does it for you. That is the whole point of a pipeline.
"""

from kedro.pipeline import Pipeline, node, pipeline

from .nodes import say_hi_at_start, create_house_data, evaluate_model, split_data, train_model


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=say_hi_at_start,
                inputs=["params:welcome_message.start"],
                outputs="welcome_message",
                name="say_hi_at_start_node"
            ),
            node(
                func=create_house_data,
                # "params:..." pulls values from conf/base/parameters.yml
                inputs=["params:n_houses", "params:seed", "welcome_message"],
                outputs="house_data",           # saved as a CSV (see catalog.yml)
                name="create_house_data_node",
            ),
            node(
                func=split_data,
                inputs=["house_data", "params:model_options"],
                outputs=["X_train", "X_test", "y_train", "y_test"],
                name="split_data_node",
            ),
            node(
                func=train_model,
                inputs=["X_train", "y_train"],
                outputs="regressor",            # the trained model, saved to disk
                name="train_model_node",
            ),
            node(
                func=evaluate_model,
                inputs=["regressor", "X_test", "y_test"],
                outputs="metrics",              # saved as a JSON file
                name="evaluate_model_node",
            ),

            node(
                func=say_hi_at_start,
                inputs=["params:welcome_message.end", "metrics"],  # depends on evaluate_model_node
                outputs="say_hi_at_end",
                name="say_hi_at_end_node"
            )
        ]
    )
