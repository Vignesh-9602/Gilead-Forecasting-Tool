import { expect, afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import * as matchers from '@testing-library/jest-dom/matchers';

expect.extend(matchers);

global.HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    // Implement your mocked getContext behavior here, if needed
}));

// Mock the canvas npm package if Plotly.js requires it
vi.mock('canvas', () => ({
    createContext: vi.fn(),
}));

// setup.js

window.URL.createObjectURL = vi.fn();

afterEach(() => {
    cleanup();
});
