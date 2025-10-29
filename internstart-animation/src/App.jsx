import React from 'react';
import { JobApplicationForm } from './JobApplicationForm';

function App() {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      background: '#fafafa',
      padding: '40px'
    }}>
      <JobApplicationForm isAnimating={true} onComplete={() => console.log('✅ Animation Complete')} />
    </div>
  );
}

export default App;
