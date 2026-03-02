;; Python tag queries — definitions and references

;; Function definitions
(function_definition
  name: (identifier) @name.definition.function) @definition.function

;; Class definitions
(class_definition
  name: (identifier) @name.definition.class) @definition.class

;; Method definitions (inside class body)
(class_definition
  body: (block
    (function_definition
      name: (identifier) @name.definition.method))) @definition.method

;; Decorated definitions
(decorated_definition
  (function_definition
    name: (identifier) @name.definition.function)) @definition.function

(decorated_definition
  (class_definition
    name: (identifier) @name.definition.class)) @definition.class

;; Function calls
(call
  function: (identifier) @name.reference.call) @reference.call

;; Method calls
(call
  function: (attribute
    attribute: (identifier) @name.reference.call)) @reference.call

;; Import statements
(import_from_statement
  name: (dotted_name) @name.reference.import) @reference.import

(import_statement
  name: (dotted_name) @name.reference.import) @reference.import

;; Assignments (top-level module constants)
(module
  (assignment
    left: (identifier) @name.definition.variable)) @definition.variable
