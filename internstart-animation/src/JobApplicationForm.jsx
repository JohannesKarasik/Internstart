import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card } from './ui/card';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Button } from './ui/button';
import { CustomProgress } from './CustomProgress';
import { Badge } from './ui/badge';
import { CheckCircle2, Loader2 } from 'lucide-react';

const formSteps = [
  { field: 'fullName', label: 'Full Name', value: 'Sarah Chen', delay: 500 },
  { field: 'email', label: 'Email', value: 'sarah.chen@email.com', delay: 1200 },
  { field: 'position', label: 'Position', value: 'Senior Software Engineer', delay: 1900 },
  { field: 'experience', label: 'Years of Experience', value: '5 years', delay: 2600 },
  {
    field: 'coverLetter',
    label: 'Cover Letter',
    value:
      'I am excited to apply for the Senior Software Engineer position. With over 5 years of experience in full-stack development, I have successfully led multiple projects from conception to deployment. My expertise includes React, Node.js, and cloud architecture. I am passionate about building scalable applications and mentoring junior developers. I believe my skills and experience make me an excellent fit for your team.',
    delay: 3300,
  },
];

/**
 * @param {{ isAnimating: boolean, onComplete: Function }} props
 */
export function JobApplicationForm({ isAnimating, onComplete }) {
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    position: '',
    experience: '',
    coverLetter: '',
  });

  const [currentStep, setCurrentStep] = useState(-1);
  const [isTyping, setIsTyping] = useState(false);
  const [completedFields, setCompletedFields] = useState(new Set());
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    if (!isAnimating) return;

    formSteps.forEach((step, index) => {
      setTimeout(() => {
        setCurrentStep(index);
        setIsTyping(true);
        animateTyping(step.field, step.value);
      }, step.delay);
    });
  }, [isAnimating]);

  const animateTyping = (field, text) => {
    let currentText = '';
    const typingSpeed = field === 'coverLetter' ? 15 : 30;

    const interval = setInterval(() => {
      if (currentText.length < text.length) {
        currentText = text.substring(0, currentText.length + 1);
        setFormData(prev => ({ ...prev, [field]: currentText }));
      } else {
        clearInterval(interval);
        setIsTyping(false);
        setCompletedFields(prev => new Set(prev).add(field));

        const allFields = formSteps.map(s => s.field);
        const newCompleted = new Set(completedFields).add(field);
        if (allFields.every(f => newCompleted.has(f))) {
          setTimeout(() => {
            setIsComplete(true);
            if (onComplete) onComplete();
          }, 500);
        }
      }
    }, typingSpeed);
  };

  const progress = (completedFields.size / formSteps.length) * 100;
  const currentFieldName = currentStep >= 0 ? formSteps[currentStep]?.field : '';

  return (
    <Card className="p-6 shadow-xl bg-white/80 backdrop-blur" style={{ borderColor: '#FF2F5A' }}>
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <h2 style={{ color: '#FF2F5A' }}>Job Application Form</h2>
          <AnimatePresence>
            {isComplete ? (
              <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5" style={{ color: '#ff5400' }} />
                <Badge className="bg-green-100 text-green-800 border-green-300">Complete</Badge>
              </motion.div>
            ) : isAnimating ? (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" style={{ color: '#FF2F5A' }} />
                <Badge style={{ backgroundColor: '#FFF0F3', color: '#FF2F5A', borderColor: '#FF2F5A' }}>
                  AI Filling...
                </Badge>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
        <CustomProgress value={progress} className="h-2" />
        <p className="text-sm mt-2" style={{ color: '#ff5400' }}>
          {isComplete ? 'Application completed!' : `${completedFields.size} of ${formSteps.length} fields completed`}
        </p>
      </div>

      <div className="space-y-4">
        {formSteps.map(step => (
          <FormField
            key={step.field}
            label={step.label}
            field={step.field}
            value={formData[step.field]}
            isActive={currentFieldName === step.field}
            isCompleted={completedFields.has(step.field)}
            isTyping={isTyping && currentFieldName === step.field}
          >
            {step.field === 'coverLetter' ? (
              <Textarea value={formData[step.field]} readOnly className="bg-white min-h-[120px] resize-none" />
            ) : (
              <Input value={formData[step.field]} readOnly className="bg-white" />
            )}
          </FormField>
        ))}

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: isComplete ? 1 : 0.5 }} transition={{ duration: 0.3 }}>
          <Button
            className="w-full"
            style={{
              backgroundColor: isComplete ? '#FF2F5A' : '#FFB3C6',
              color: 'white',
            }}
            disabled={!isComplete}
            onMouseEnter={e => {
              if (isComplete) e.currentTarget.style.backgroundColor = '#ff5400';
            }}
            onMouseLeave={e => {
              if (isComplete) e.currentTarget.style.backgroundColor = '#FF2F5A';
            }}
          >
            Submit Application
          </Button>
        </motion.div>
      </div>
    </Card>
  );
}

function FormField({ label, field, value, isActive, isCompleted, isTyping, children }) {
  return (
    <motion.div
      initial={{ opacity: 0.5, scale: 0.98 }}
      animate={{
        opacity: isActive ? 1 : isCompleted ? 1 : 0.6,
        scale: isActive ? 1.02 : 1,
        borderColor: isActive ? '#FF2F5A' : isCompleted ? '#ff5400' : '#e5e7eb',
      }}
      transition={{ duration: 0.3 }}
      className="relative space-y-1.5 p-3 rounded-lg border-2 transition-colors"
      style={{ backgroundColor: isActive ? 'rgba(255, 47, 90, 0.1)' : 'transparent' }}
    >
      <div className="flex items-center justify-between">
        <Label className="text-gray-700">{label}</Label>
        <AnimatePresence>
          {isCompleted && (
            <motion.div
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              exit={{ scale: 0 }}
              transition={{ type: 'spring', stiffness: 200, damping: 15 }}
            >
              <CheckCircle2 className="w-4 h-4" style={{ color: '#ff5400' }} />
            </motion.div>
          )}
          {isTyping && isActive && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{ duration: 1, repeat: Infinity }}
              className="flex gap-1"
            >
              <span className="w-1 h-1 rounded-full" style={{ backgroundColor: '#FF2F5A' }}></span>
              <span className="w-1 h-1 rounded-full" style={{ backgroundColor: '#FF2F5A' }}></span>
              <span className="w-1 h-1 rounded-full" style={{ backgroundColor: '#FF2F5A' }}></span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      {children}
    </motion.div>
  );
}
