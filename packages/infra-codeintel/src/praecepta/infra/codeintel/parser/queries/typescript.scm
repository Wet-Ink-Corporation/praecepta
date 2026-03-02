;; TypeScript tag queries — definitions and references

;; Function declarations
(function_declaration
  name: (identifier) @name.definition.function) @definition.function

;; Class declarations
(class_declaration
  name: (type_identifier) @name.definition.class) @definition.class

;; Method definitions
(method_definition
  name: (property_identifier) @name.definition.method) @definition.method

;; Arrow functions assigned to variables
(lexical_declaration
  (variable_declarator
    name: (identifier) @name.definition.function
    value: (arrow_function))) @definition.function

;; Interface declarations
(interface_declaration
  name: (type_identifier) @name.definition.interface) @definition.interface

;; Type alias declarations
(type_alias_declaration
  name: (type_identifier) @name.definition.type) @definition.type

;; Enum declarations
(enum_declaration
  name: (identifier) @name.definition.enum) @definition.enum

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
    name: (type_identifier) @name.definition.class)) @definition.class
