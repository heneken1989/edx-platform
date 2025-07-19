// Payment Page React Component Loader
(function() {
    'use strict';

    // Check if React is available
    if (typeof React === 'undefined') {
        console.error('React is not loaded. Payment page cannot be rendered.');
        return;
    }

    // Simple React component for payment page
    const PaymentPage = React.createClass({
        getInitialState: function() {
            return {
                courseData: {
                    courseId: 'CS101',
                    courseName: 'Introduction to Computer Science',
                    price: 500000, // 500,000 VND
                    instructor: 'Dr. John Smith',
                    duration: '8 weeks',
                    level: 'Beginner'
                },
                paymentMethod: 'vnpay',
                isProcessing: false
            };
        },

        handlePayment: function() {
            this.setState({ isProcessing: true });
            
            const paymentData = {
                amount: this.state.courseData.price,
                courseId: this.state.courseData.courseId,
                courseName: this.state.courseData.courseName,
                currency: 'VND',
                paymentMethod: this.state.paymentMethod,
                returnUrl: window.PAYMENT_PAGE_PROPS.successUrl,
                cancelUrl: window.PAYMENT_PAGE_PROPS.cancelUrl
            };

            // Call backend API
            fetch(window.PAYMENT_PAGE_PROPS.apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(paymentData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.paymentUrl) {
                    window.location.href = data.paymentUrl;
                } else {
                    alert('Payment failed. Please try again.');
                }
            })
            .catch(error => {
                console.error('Payment error:', error);
                alert('Payment failed. Please try again.');
            })
            .finally(() => {
                this.setState({ isProcessing: false });
            });
        },

        getCSRFToken: function() {
            const name = 'csrftoken';
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        },

        formatPrice: function(price) {
            return new Intl.NumberFormat('vi-VN', {
                style: 'currency',
                currency: 'VND'
            }).format(price);
        },

        render: function() {
            const { courseData, paymentMethod, isProcessing } = this.state;

            return React.createElement('div', { className: 'payment-page' },
                React.createElement('div', { className: 'payment-container' },
                    React.createElement('div', { className: 'payment-header' },
                        React.createElement('h1', null, 'Thanh toán khóa học'),
                        React.createElement('p', null, 'Hoàn tất đăng ký khóa học của bạn')
                    ),
                    React.createElement('div', { className: 'payment-content' },
                        React.createElement('div', { className: 'course-summary' },
                            React.createElement('h2', null, 'Thông tin khóa học'),
                            React.createElement('div', { className: 'course-card' },
                                React.createElement('div', { className: 'course-info' },
                                    React.createElement('h3', null, courseData.courseName),
                                    React.createElement('div', { className: 'course-details' },
                                        React.createElement('p', null, 
                                            React.createElement('strong', null, 'Mã khóa học: '), 
                                            courseData.courseId
                                        ),
                                        React.createElement('p', null, 
                                            React.createElement('strong', null, 'Giảng viên: '), 
                                            courseData.instructor
                                        ),
                                        React.createElement('p', null, 
                                            React.createElement('strong', null, 'Thời lượng: '), 
                                            courseData.duration
                                        ),
                                        React.createElement('p', null, 
                                            React.createElement('strong', null, 'Trình độ: '), 
                                            courseData.level
                                        )
                                    )
                                ),
                                React.createElement('div', { className: 'course-price' },
                                    React.createElement('span', { className: 'price' }, 
                                        this.formatPrice(courseData.price)
                                    )
                                )
                            )
                        ),
                        React.createElement('div', { className: 'payment-method' },
                            React.createElement('h2', null, 'Phương thức thanh toán'),
                            React.createElement('div', { className: 'payment-options' },
                                React.createElement('label', { className: 'payment-option' },
                                    React.createElement('input', {
                                        type: 'radio',
                                        name: 'paymentMethod',
                                        value: 'vnpay',
                                        checked: paymentMethod === 'vnpay',
                                        onChange: (e) => this.setState({ paymentMethod: e.target.value })
                                    }),
                                    React.createElement('div', { className: 'option-content' },
                                        React.createElement('img', { 
                                            src: 'https://vnpay.vn/wp-content/uploads/2020/07/logo-vnpay.png', 
                                            alt: 'VNPay' 
                                        }),
                                        React.createElement('span', null, 'VNPay')
                                    )
                                ),
                                React.createElement('label', { className: 'payment-option' },
                                    React.createElement('input', {
                                        type: 'radio',
                                        name: 'paymentMethod',
                                        value: 'momo',
                                        checked: paymentMethod === 'momo',
                                        onChange: (e) => this.setState({ paymentMethod: e.target.value })
                                    }),
                                    React.createElement('div', { className: 'option-content' },
                                        React.createElement('img', { 
                                            src: 'https://developers.momo.vn/assets/images/logo-momo.png', 
                                            alt: 'MoMo' 
                                        }),
                                        React.createElement('span', null, 'MoMo')
                                    )
                                )
                            )
                        ),
                        React.createElement('div', { className: 'payment-summary' },
                            React.createElement('h2', null, 'Tổng thanh toán'),
                            React.createElement('div', { className: 'summary-item' },
                                React.createElement('span', null, 'Giá khóa học:'),
                                React.createElement('span', null, this.formatPrice(courseData.price))
                            ),
                            React.createElement('div', { className: 'summary-item' },
                                React.createElement('span', null, 'Phí giao dịch:'),
                                React.createElement('span', null, this.formatPrice(0))
                            ),
                            React.createElement('div', { className: 'summary-item total' },
                                React.createElement('span', null, 'Tổng cộng:'),
                                React.createElement('span', null, this.formatPrice(courseData.price))
                            )
                        ),
                        React.createElement('div', { className: 'payment-actions' },
                            React.createElement('button', {
                                className: 'btn-pay',
                                onClick: this.handlePayment,
                                disabled: isProcessing
                            }, isProcessing ? 'Đang xử lý...' : 'Thanh toán ngay'),
                            React.createElement('button', {
                                className: 'btn-cancel',
                                onClick: () => window.location.href = '/dashboard'
                            }, 'Hủy bỏ')
                        )
                    )
                )
            );
        }
    });

    // Render the component when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        const container = document.getElementById('payment-page-root');
        if (container) {
            ReactDOM.render(React.createElement(PaymentPage), container);
        }
    });

})(); 