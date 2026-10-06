// Changes in this file will take effect after running npx webpack.
// Please refer to the README for a guide on how to do this.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { withTheme } from '@rjsf/core';
import { Theme as Bootstrap4Theme } from '@rjsf/react-bootstrap';
import validator from '@rjsf/validator-ajv8';
import { getDefaultFormState } from "@rjsf/utils";
import AltDateWidget from "./alt_date_widget";
import './alt_date_widget.css';

const Form = withTheme(Bootstrap4Theme);
const DefaultFieldTemplate = Bootstrap4Theme.templates.FieldTemplate;

// Store roots by element id
const roots = {};
const formRef = React.createRef();

const widgets = {
    'alt-date': AltDateWidget
};

function FieldTemplate(props) {
    const { uiSchema, id, label, rawErrors, required, description, rawDescription, displayLabel, errors, help, children } = props;

    const widget = uiSchema && uiSchema["ui:widget"];
    const isAltDateWidget = widget === "alt-date" || widget === "alt-date-time";

    if (!isAltDateWidget) {
        // For all non-alt-date fields, use the theme's default FieldTemplate
        return <DefaultFieldTemplate {...props} />;
    }

    const hasErrors = Array.isArray(rawErrors) && rawErrors.length > 0;

    // Custom layout for alt-date / alt-date-time
    return (
        <fieldset className="form-group alt-date-field" id={id}>
            {label && (
                <legend className="form-label m-0">
                    {label}
                    {required && <span className="required">*</span>}
                </legend>
            )}

            {children}
            {displayLabel && rawDescription  && (
                <small className={hasErrors ? 'text-danger' : 'text-muted'}>{description}</small>
            )}
            {errors}
            {help}
        </fieldset>
    );
}

function DescriptionFieldTemplate(props) {
    const { description, id, schema } = props;
    const tooltipText = schema["tooltip"];
    return (
        <div id={id}>
            {description}
            {tooltipText ? (<span tabIndex="0" aria-label={tooltipText} title={tooltipText}><i class="fa-solid fa-circle-info"></i></span>) : null}
        </div>
    );
}

// Not currently used, but could be convenient to have?
window.ValidateRjsfFormData = function () {
    console.log("validating")
    return formRef.current.validateForm()

}

// This function renders the form in the given element.
// It should be available globally so your template JS can call it.
window.renderJsonSchemaForm = function ({ schema, uiSchema, formData, elementId, onChange, onSubmit, onError, formId, afterInitFunction }) {
    const el = document.getElementById(elementId);
    if (!el) return;

    // Create a root if it doesn't exist for this element
    if (!roots[elementId]) {
        roots[elementId] = createRoot(el);
    }

    // Pass the default data to the renderer, to prevent OnChange before entering data
    const effectiveFormData = getDefaultFormState(
        validator,
        schema,
        formData || {}
    );

    roots[elementId].render(
        React.createElement(
            Form,
            {
                id: formId,
                schema: schema,
                uiSchema: uiSchema,
                formData: effectiveFormData,
                onChange: onChange,
                templates: {
                    DescriptionFieldTemplate,
                    FieldTemplate,
                },
                onSubmit: onSubmit,
                validator: validator,
                widgets: widgets,
                onError: onError,
                ref: formRef
            },
            React.createElement("div", null)
        )
    );
    afterInitFunction();
};

window.unmountJsonSchemaForm = function ({ elementId }) {
    if (roots.hasOwnProperty(elementId)) {
        roots[elementId].unmount();
        delete roots[elementId];
    }
};