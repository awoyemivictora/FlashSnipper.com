import React from 'react';

interface EditTextProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: 'text' | 'email' | 'number';
  disabled?: boolean;
  className?: string;
  label?: string;
}

const EditText: React.FC<EditTextProps> = ({
  value,
  onChange,
  placeholder = '',
  type = 'text',
  disabled = false,
  className = '',
  label
}) => {
  return (
    <div className={`flex flex-col ${className}`}>
      {label && (
        <label className="text-light text-sm font-medium mb-2">
          {label}
        </label>
      )}
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className={`
          px-3 py-2 bg-secondary border border-accent rounded-lg
          text-white placeholder-muted
          focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      />
    </div>
  );
};

export default EditText;