// @ts-nocheck
/**
 * preact-setup.js — Single import shim for all components.
 * Binds htm to Preact's h and re-exports every Preact primitive in common use.
 * Components import from this file only; update the path here if the dep changes.
 */

import { h, render, Fragment, createContext } from './preact.module.js';
import { useState, useEffect, useReducer, useRef, useMemo, useCallback } from './preact-hooks.module.js';
import htm from './htm.module.js';

/** @type {function(TemplateStringsArray, ...any): any} */
export const html = htm.bind(h);

/** @type {typeof h} */
export { h };
/** @type {typeof render} */
export { render };
/** @type {typeof Fragment} */
export { Fragment };
/** @type {typeof createContext} */
export { createContext };
/** @type {typeof useState} */
export { useState };
/** @type {typeof useEffect} */
export { useEffect };
/** @type {typeof useReducer} */
export { useReducer };
/** @type {typeof useRef} */
export { useRef };
/** @type {typeof useMemo} */
export { useMemo };
/** @type {typeof useCallback} */
export { useCallback };
