import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LandingPage from '../../pages/LandingPage';
import { vi } from 'vitest';
import { GlobalContext } from '../../context/Provider';

// mock api
vi.mock('../../services/apiService', () => ({
    getTherapyAreaList: vi.fn(),
}));

import { getTherapyAreaList } from '../../services/apiService';

// mock navigate
const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    };
});

const renderComponent = () => {
    return render(
        <GlobalContext.Provider value={{ favDispatch: vi.fn() }}>
            <MemoryRouter>
                <LandingPage />
            </MemoryRouter>
        </GlobalContext.Provider>
    );
};
describe('LandingPage', () => {
    beforeEach(() => {
        vi.clearAllMocks();

        getTherapyAreaList.mockResolvedValue({
            data: {
                ta_list: ['Oncology', 'PBC'],
            },
        });
    });

    it('checks landing page test id exists', async () => {
        renderComponent();

        await waitFor(() => {
            expect(screen.getByTestId('landing-page')).toBeInTheDocument();
        });
    });

    it('checks Select Therapeutic Area text exists', async () => {
        renderComponent();

        await waitFor(() => {
            expect(screen.getByText('Select Therapeutic Area')).toBeInTheDocument();
        });
    });

    it('renders api response cards', async () => {
        renderComponent();

        await waitFor(() => {
            expect(screen.getByText('Oncology')).toBeInTheDocument();
            expect(screen.getByText('PBC')).toBeInTheDocument();
        });
    });

    it('clicks oncology card', async () => {
        renderComponent();

        await waitFor(() => {
            expect(screen.getByText('Oncology')).toBeInTheDocument();
        });

        fireEvent.click(screen.getByText('Oncology'));

        expect(mockNavigate).toHaveBeenCalledWith('/app');
    });
});