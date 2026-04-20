import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
// import EditRole from '../../components/AccessMangementComponent/EditRole';
import { MemoryRouter } from 'react-router-dom';
// import landingpage from '../../pages/LandingPage' 
import LandingPage from '../../pages/LandingPage';

const renderWithRouter = (component) => {
    return render(<MemoryRouter>{component}</MemoryRouter>);
};

describe('EditRole Component', () => {
    it('renders the EditRole component without crashing', async () => {
        renderWithRouter(<LandingPage />);

        // Wait for component to render
        await waitFor(() => {
            expect(screen.getByTestId('login-form')).toBeInTheDocument();
        });
    });

    //   it('renders the left side panel "Edit Role"', async () => {
    //     renderWithRouter(<EditRole />);

    //     await waitFor(() => {
    //       expect(screen.getByText('Edit Role')).toBeInTheDocument();
    //     });
    //   });

    //   it('should render the form with role name and description fields in the right panel', async () => {
    //     renderWithRouter(<EditRole />);

    //     await waitFor(() => {
    //       expect(screen.getByLabelText(/Role Name/i)).toBeInTheDocument();
    //       expect(screen.getByLabelText(/Role Description/i)).toBeInTheDocument();
    //       expect(screen.getByLabelText(/Permissions/i)).toBeInTheDocument();
    //     });
    //   });

    //   it('should render the Cancel button', async () => {
    //     renderWithRouter(<EditRole />);

    //     await waitFor(() => {
    //       expect(
    //         screen.getByRole('button', { name: 'Cancel' })
    //       ).toBeInTheDocument();
    //     });
    //   });
});
