;; JavaScript tag queries — shares most patterns with TypeScript
;; minus type-specific constructs (interfaces, type aliases, enums)

;; Function declarations
(function_declaration
  name: (identifier) @name.definition.function) @definition.function

;; Class declarations
(class_declaration
  name: (identifier) @name.definition.class) @definition.class

;; Method definitions
(method_definition
  name: (property_identifier) @name.definition.method) @definition.method

;; Arrow functions assigned to variables
(lexical_declaration
  (variable_declarator
    name: (identifier) @name.definition.function
    value: (arrow_function))) @definition.function

;; Variable declarations (const/let at module level)
(program
  (lexical_declaration
    (variable_declarator
      name: (identifier) @name.definition.variable))) @definition.variable

;; Function calls
(call_expression
  function: (identifier) @name.reference.call) @reference.call

;; Method calls
(call_expression
  function: (member_expression
    property: (property_identifier) @name.reference.call)) @reference.call

;; Import statements
(import_statement
  source: (string) @name.reference.import) @reference.import

;; Export declarations
(export_statement
  declaration: (function_declaration
    name: (identifier) @name.definition.function)) @definition.function

(export_statement
  declaration: (class_declaration
    name: (identifier) @name.definition.class)) @definition.class
